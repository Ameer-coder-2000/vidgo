from flask import Flask, jsonify, render_template, request, send_file
import os
import shutil
import tempfile
import threading
import time
from typing import Optional
import json

from yt_dlp import YoutubeDL

app = Flask(__name__, static_folder='static', template_folder='templates')

download_state_lock = threading.Lock()


def get_ydl_opts_base(skip_download=True):
    """Get base yt-dlp options with better YouTube support."""
    opts = {
        'quiet': True,
        'skip_download': skip_download,
        'nocheckcertificate': True,
        'socket_timeout': 120 if skip_download else 300,
        'retries': 5,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android'],
                'player_skip': ['js', 'configs'],
            }
        },
        'cookiesfrombrowser': ('chrome', 'firefox', 'chromium', 'opera', 'edge'),
    }
    
    # Add stored cookies if available
    global stored_cookies
    if stored_cookies:
        opts['cookies'] = stored_cookies
    
    return opts


# Global storage for cookies
stored_cookies = None
cookies_lock = threading.Lock()


def _idle_download_state():
    return {
        'status': 'idle',
        'mode': None,
        'percent': '0%',
        'eta': None,
        'message': '',
        'error': None,
        'tmp_dir': None,
        'filename': None,
        'download_name': None,
        'cancel_requested': False,
        'started_at': None,
        'completed_at': None,
    }


download_state = _idle_download_state()


class DownloadCancelled(Exception):
    """Raised when the user cancels an in-progress download."""


def ffmpeg_available() -> bool:
    """Return True if ffmpeg is installed and available on PATH."""
    return shutil.which('ffmpeg') is not None


def get_format_type(item: dict) -> str:
    """Return a human-friendly type label from yt-dlp format metadata."""
    vcodec = item.get('vcodec')
    acodec = item.get('acodec')
    if vcodec and vcodec != 'none' and acodec and acodec != 'none':
        return 'video+audio'
    if vcodec and vcodec != 'none':
        return 'video'
    if acodec and acodec != 'none':
        return 'audio'
    return 'other'


def is_downloadable_format(item: dict) -> bool:
    """Skip non-downloadable formats like storyboards and metadata-only entries."""
    format_id = (item.get('format_id') or '').lower()
    ext = (item.get('ext') or '').lower()
    if not format_id or not ext:
        return False
    if 'storyboard' in format_id or ext == 'mhtml':
        return False
    return get_format_type(item) != 'other'


def select_playback_url(formats):
    """Pick the best direct media URL for previewing the video."""
    playable_formats = [item for item in formats if is_downloadable_format(item) and item.get('url')]
    if not playable_formats:
        return None

    def score(item: dict):
        format_type = get_format_type(item)
        type_score = 2 if format_type == 'video+audio' else 1 if format_type == 'video' else 0
        return (
            type_score,
            item.get('height') or 0,
            item.get('width') or 0,
            item.get('tbr') or 0,
            item.get('filesize') or item.get('filesize_approx') or 0,
        )

    return max(playable_formats, key=score).get('url')


def cleanup_temp_dir(tmp_dir: Optional[str]) -> None:
    """Remove a temporary download directory if it exists."""
    if tmp_dir and os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)


def reset_download_state(clean_files: bool = False) -> None:
    """Return the shared download state back to idle."""
    with download_state_lock:
        tmp_dir = download_state.get('tmp_dir')
        download_state.clear()
        download_state.update(_idle_download_state())
    if clean_files:
        cleanup_temp_dir(tmp_dir)


def get_download_snapshot() -> dict:
    """Return a JSON-safe snapshot of the current download state."""
    with download_state_lock:
        status = download_state['status']
        return {
            'status': status,
            'mode': download_state['mode'],
            'percent': download_state['percent'],
            'eta': download_state['eta'],
            'message': download_state['message'],
            'error': download_state['error'],
            'download_ready': status == 'complete' and bool(download_state['filename']),
            'can_cancel': status in ('downloading', 'processing', 'cancelling'),
            'download_url': '/api/download/file' if status == 'complete' and download_state['filename'] else None,
        }


def resolve_downloaded_file(tmp_dir: str, preferred_filename: str):
    """Find the final downloaded file in the temp directory."""
    if preferred_filename and os.path.exists(preferred_filename):
        return preferred_filename

    candidates = []
    for name in os.listdir(tmp_dir):
        path = os.path.join(tmp_dir, name)
        if not os.path.isfile(path):
            continue
        lower_name = name.lower()
        if lower_name.endswith(('.part', '.ytdl', '.temp')):
            continue
        candidates.append(path)

    if not candidates:
        return None

    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def progress_hook(d: dict) -> None:
    """Track yt-dlp progress and honor cancellation requests."""
    with download_state_lock:
        mode_label = download_state.get('mode') or 'video'

    if d.get('status') == 'downloading':
        downloaded = d.get('downloaded_bytes') or 0
        total = d.get('total_bytes') or d.get('total_bytes_estimate')
        if total and total > 0:
            percent = f'{(downloaded / total) * 100:.1f}%'
        else:
            fragment_index = d.get('fragment_index') or 0
            fragment_count = d.get('fragment_count') or 0
            percent = f'{(fragment_index / fragment_count) * 100:.1f}%' if fragment_count else '0%'

        eta_value = d.get('eta')
        eta_seconds = int(eta_value) if isinstance(eta_value, (int, float)) and eta_value >= 0 else None

        with download_state_lock:
            if download_state['cancel_requested']:
                download_state['status'] = 'cancelling'
                download_state['message'] = f'Canceling {mode_label} download...'
                raise DownloadCancelled('Download canceled by user.')

            download_state['status'] = 'downloading'
            download_state['percent'] = percent
            download_state['eta'] = eta_seconds
            download_state['message'] = f'Downloading {mode_label}...'

    elif d.get('status') == 'finished':
        with download_state_lock:
            if download_state['cancel_requested']:
                download_state['status'] = 'cancelling'
                download_state['message'] = f'Canceling {mode_label} download...'
                raise DownloadCancelled('Download canceled by user.')

            download_state['status'] = 'processing'
            download_state['percent'] = '100%'
            download_state['eta'] = 0
            download_state['message'] = f'Finalizing {mode_label} download...'


def get_download_format_selector(mode: str) -> str:
    """Choose the yt-dlp format selector for the requested download mode."""
    if mode == 'audio':
        return 'bestaudio'
    if ffmpeg_available():
        return 'bestvideo+bestaudio/best'
    return 'best'


def run_download_job(url: str, mode: str) -> None:
    """Run the actual yt-dlp download in a background thread."""
    mode = 'audio' if mode == 'audio' else 'video'
    tmp_dir = tempfile.mkdtemp(prefix='uva_')
    with download_state_lock:
        cancel_requested = download_state.get('cancel_requested', False)
        download_state['tmp_dir'] = tmp_dir
        download_state['mode'] = mode
        download_state['status'] = 'cancelling' if cancel_requested else 'downloading'
        download_state['percent'] = '0%'
        download_state['eta'] = None
        download_state['message'] = f"Canceling {mode} download..." if cancel_requested else f"Preparing {mode} download..."
        download_state['error'] = None
        download_state['filename'] = None
        download_state['download_name'] = None
        download_state['cancel_requested'] = cancel_requested
        download_state['started_at'] = time.time()
        download_state['completed_at'] = None

    if cancel_requested:
        raise DownloadCancelled('Download canceled by user.')

    ydl_opts = get_ydl_opts_base(skip_download=False)
    ydl_opts['format'] = get_download_format_selector(mode)
    ydl_opts['outtmpl'] = os.path.join(tmp_dir, '%(title)s.%(ext)s')
    ydl_opts['progress_hooks'] = [progress_hook]

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError('yt-dlp returned no info')

            with download_state_lock:
                if download_state['cancel_requested']:
                    raise DownloadCancelled('Download canceled by user.')

            preferred_filename = ydl.prepare_filename(info)

        filename = resolve_downloaded_file(tmp_dir, preferred_filename)
        if not filename:
            raise FileNotFoundError('Downloaded file could not be located.')

        with download_state_lock:
            download_state['status'] = 'complete'
            download_state['percent'] = '100%'
            download_state['eta'] = 0
            download_state['message'] = f'{mode.title()} download complete.'
            download_state['error'] = None
            download_state['filename'] = filename
            download_state['download_name'] = os.path.basename(filename)
            download_state['completed_at'] = time.time()
            download_state['cancel_requested'] = False

    except DownloadCancelled:
        cleanup_temp_dir(tmp_dir)
        with download_state_lock:
            download_state['status'] = 'canceled'
            download_state['mode'] = None
            download_state['percent'] = '0%'
            download_state['eta'] = None
            download_state['message'] = 'Download canceled.'
            download_state['error'] = None
            download_state['filename'] = None
            download_state['download_name'] = None
            download_state['tmp_dir'] = None
            download_state['cancel_requested'] = False
            download_state['completed_at'] = time.time()
    except Exception as e:
        cleanup_temp_dir(tmp_dir)
        with download_state_lock:
            download_state['status'] = 'error'
            download_state['mode'] = None
            download_state['percent'] = '0%'
            download_state['eta'] = None
            download_state['message'] = 'Download failed.'
            download_state['error'] = str(e)
            download_state['filename'] = None
            download_state['download_name'] = None
            download_state['tmp_dir'] = None
            download_state['cancel_requested'] = False
            download_state['completed_at'] = time.time()


@app.route('/')
def index():
    """Render the frontend page."""
    return render_template('index.html')


@app.route('/api/cookies', methods=['POST'])
def set_cookies():
    """Store YouTube cookies for authentication."""
    global stored_cookies
    data = request.get_json() or {}
    cookies = data.get('cookies')
    
    if not cookies:
        return jsonify({'error': 'No cookies provided.'}), 400
    
    with cookies_lock:
        stored_cookies = cookies
    
    return jsonify({'status': 'success', 'message': 'Cookies updated successfully.'}), 200


@app.route('/api/cookies', methods=['GET'])
def get_cookies_status():
    """Check if cookies are configured."""
    global stored_cookies
    with cookies_lock:
        has_cookies = stored_cookies is not None
    return jsonify({'has_cookies': has_cookies}), 200


@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    """Analyze the submitted video URL and return metadata."""
    data = request.get_json() or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Please provide a video URL.'}), 400

    ydl_opts = get_ydl_opts_base(skip_download=True)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({'error': f'Failed to analyze URL: {str(e)}', 'platform': 'Unknown'}), 400

    extractor_key = info.get('extractor_key', 'Unknown')
    platform = extractor_key.replace('_', ' ').title()

    return jsonify({
        'platform': platform,
        'title': info.get('title', 'Unknown title'),
        'thumbnail': info.get('thumbnail'),
        'duration': info.get('duration'),
        'uploader': info.get('uploader') or info.get('channel'),
        'webpage_url': info.get('webpage_url'),
        'playback_url': select_playback_url(info.get('formats') or []) or info.get('url'),
        'id': info.get('id'),
    })


@app.route('/api/progress')
def get_progress():
    """Get current download progress."""
    return jsonify(get_download_snapshot())


@app.route('/api/download', methods=['POST'])
def download_video():
    """Start a background download for the selected media mode."""
    data = request.get_json(silent=True) or request.form or {}
    url = data.get('url', '').strip()
    download_mode = (data.get('download_mode') or '').strip().lower()
    format_id = (data.get('format_id') or '').strip().lower()

    if not url:
        error_msg = 'Missing URL for download.'
        return jsonify({'error': error_msg}), 400

    if download_mode not in ('video', 'audio'):
        if 'audio' in format_id:
            download_mode = 'audio'
        else:
            download_mode = 'video'

    with download_state_lock:
        status = download_state['status']
        if status in ('downloading', 'processing', 'cancelling'):
            return jsonify({'error': 'A download is already in progress. Cancel it first.'}), 409

        if status == 'complete':
            completed_at = download_state.get('completed_at')
            if not completed_at or (time.time() - completed_at) < 900:
                return jsonify({'error': 'A completed download is waiting to be saved. Please finish it first.'}), 409
            stale_tmp_dir = download_state.get('tmp_dir')
            download_state.clear()
            download_state.update(_idle_download_state())
        elif status in ('canceled', 'error'):
            stale_tmp_dir = download_state.get('tmp_dir')
            download_state.clear()
            download_state.update(_idle_download_state())
        else:
            stale_tmp_dir = None

    if stale_tmp_dir:
        cleanup_temp_dir(stale_tmp_dir)

    worker = threading.Thread(target=run_download_job, args=(url, download_mode), daemon=True)
    worker.start()

    return jsonify({'status': 'started', 'message': f'{download_mode.title()} download started in the background.'}), 202


@app.route('/api/download/cancel', methods=['POST'])
def cancel_download():
    """Cancel the active download if one is running."""
    with download_state_lock:
        if download_state['status'] not in ('downloading', 'processing', 'cancelling'):
            return jsonify({'error': 'No active download to cancel.'}), 400

        mode = download_state.get('mode') or 'video'
        download_state['cancel_requested'] = True
        download_state['status'] = 'cancelling'
        download_state['message'] = f'Canceling {mode} download...'
        download_state['completed_at'] = None

    return jsonify({'status': 'cancelling', 'message': f'Canceling {mode} download...'})


@app.route('/api/download/file')
def download_file():
    """Send the completed download file to the browser."""
    with download_state_lock:
        if download_state['status'] != 'complete' or not download_state['filename']:
            return jsonify({'error': 'No completed download is ready yet.'}), 409

        filename = download_state['filename']
        download_name = download_state.get('download_name') or os.path.basename(filename)
        tmp_dir = download_state.get('tmp_dir')

    # Release the shared download slot immediately so the next download can start
    # while this response is still streaming to the browser.
    reset_download_state(clean_files=False)

    if not os.path.exists(filename):
        return jsonify({'error': 'The downloaded file could not be found on disk.'}), 500

    response = send_file(
        filename,
        as_attachment=True,
        download_name=download_name,
        mimetype='application/octet-stream',
    )

    @response.call_on_close
    def cleanup_after_send():
        cleanup_temp_dir(tmp_dir)

    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
