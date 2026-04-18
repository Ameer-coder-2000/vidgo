const videoUrl = document.getElementById('videoUrl');
const analyzeBtn = document.getElementById('analyzeBtn');
const viewVideoBtn = document.getElementById('viewVideoBtn');
const downloadVideoBtn = document.getElementById('downloadVideoBtn');
const downloadAudioBtn = document.getElementById('downloadAudioBtn');
const copyInfoBtn = document.getElementById('copyInfoBtn');
const cancelDownloadBtn = document.getElementById('cancelDownloadBtn');
const darkModeToggle = document.getElementById('darkModeToggle');
const loader = document.getElementById('loader');
const statusText = document.getElementById('statusText');
const resultSection = document.getElementById('resultSection');
const errorCard = document.getElementById('errorCard');
const errorMessage = document.getElementById('errorMessage');
const thumbnailImage = document.getElementById('thumbnailImage');
const videoPreviewContainer = document.getElementById('videoPreviewContainer');
const videoPreview = document.getElementById('videoPreview');
const closePreviewBtn = document.getElementById('closePreviewBtn');
const videoTitle = document.getElementById('videoTitle');
const platformInfo = document.getElementById('platformInfo');
const durationInfo = document.getElementById('durationInfo');
const uploaderInfo = document.getElementById('uploaderInfo');
const downloadProgress = document.getElementById('downloadProgress');
const progressLabel = document.getElementById('progressLabel');
const progressFill = document.getElementById('progressFill');
const progressPercent = document.getElementById('progressPercent');
const progressEta = document.getElementById('progressEta');
const cookiesInput = document.getElementById('cookiesInput');
const setCookiesBtn = document.getElementById('setCookiesBtn');
const cookiesStatus = document.getElementById('cookiesStatus');

let currentVideoData = null;
let downloadPollInterval = null;
let downloadInProgress = false;
let currentDownloadMode = null;
let downloadTriggered = false;

function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || seconds === '') {
        return 'Unknown duration';
    }

    const totalSeconds = Number(seconds);
    if (!Number.isFinite(totalSeconds)) {
        return 'Unknown duration';
    }

    const minutes = Math.floor(totalSeconds / 60);
    const remain = Math.floor(totalSeconds % 60);
    return `${minutes}m ${remain}s`;
}

function showLoader(active) {
    loader.classList.toggle('hidden', !active);
    analyzeBtn.disabled = active;
    statusText.textContent = active ? 'Analyzing...' : '';
}

function clearDownloadPolling() {
    if (downloadPollInterval) {
        clearInterval(downloadPollInterval);
        downloadPollInterval = null;
    }
}

function setDownloadControls(active, mode = null) {
    downloadInProgress = active;
    currentDownloadMode = active ? mode : null;
    downloadVideoBtn.disabled = active;
    downloadAudioBtn.disabled = active;
    cancelDownloadBtn.disabled = !active;
    downloadVideoBtn.textContent = active && mode === 'video' ? 'Downloading Video...' : 'Download Video';
    downloadAudioBtn.textContent = active && mode === 'audio' ? 'Downloading Audio...' : 'Download Audio';
}

function showError(message, options = {}) {
    const { hideResults = true, hideProgress = true } = options;
    errorMessage.textContent = message;
    errorCard.classList.remove('hidden');
    if (hideResults) {
        resultSection.classList.add('hidden');
    }
    if (hideProgress) {
        hideDownloadProgress();
    }
}

function clearError() {
    errorCard.classList.add('hidden');
    errorMessage.textContent = '';
}

function showDownloadProgress() {
    const modeLabel = currentDownloadMode === 'audio' ? 'audio' : currentDownloadMode === 'video' ? 'video' : 'download';
    downloadProgress.classList.remove('hidden');
    progressFill.style.width = '0%';
    progressPercent.textContent = '0%';
    progressEta.textContent = 'ETA: --:--';
    progressLabel.textContent = `Preparing ${modeLabel} download...`;
}

function hideDownloadProgress() {
    downloadProgress.classList.add('hidden');
    progressFill.style.width = '0%';
    progressPercent.textContent = '0%';
    progressEta.textContent = 'ETA: --:--';
    progressLabel.textContent = 'Downloading...';
}

function flashStatus(message, duration = 3000) {
    statusText.textContent = message;
    if (duration > 0) {
        setTimeout(() => {
            if (statusText.textContent === message) {
                statusText.textContent = '';
            }
        }, duration);
    }
}

function getPreviewUrl() {
    return currentVideoData?.playback_url || null;
}

function closePreview() {
    if (videoPreview) {
        videoPreview.pause();
        videoPreview.removeAttribute('src');
        videoPreview.load();
    }
    videoPreviewContainer.classList.add('hidden');
}

function openPreviewOrSource() {
    if (!currentVideoData) {
        showError('Analyze a video first.', { hideResults: false });
        return;
    }

    const previewUrl = getPreviewUrl();
    if (previewUrl) {
        videoPreview.src = previewUrl;
        videoPreviewContainer.classList.remove('hidden');
        videoPreview.load();
        videoPreviewContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        clearError();
        return;
    }

    if (currentVideoData.webpage_url) {
        window.open(currentVideoData.webpage_url, '_blank', 'noopener,noreferrer');
        flashStatus('Opened the source page in a new tab.', 2500);
        return;
    }

    showError('No playable preview is available for this video.', { hideResults: false });
}

function updateResult(data) {
    currentVideoData = data;
    closePreview();
    thumbnailImage.src = data.thumbnail || '';
    thumbnailImage.alt = data.title;
    videoTitle.textContent = data.title;
    platformInfo.textContent = `Platform: ${data.platform}`;
    durationInfo.textContent = `Duration: ${formatDuration(data.duration)}`;
    uploaderInfo.textContent = data.uploader ? `Uploader: ${data.uploader}` : 'Uploader: Unknown';

    resultSection.classList.remove('hidden');
    clearError();
}

async function analyzeUrl() {
    if (downloadInProgress) {
        showError('Finish or cancel the current download before analyzing another video.', { hideResults: false });
        return;
    }

    clearError();
    const url = videoUrl.value.trim();

    if (!url) {
        showError('Please enter a valid video URL.', { hideResults: false });
        return;
    }

    showLoader(true);

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });

        const result = await response.json();
        if (!response.ok) {
            showError(result.error || 'Analysis failed.');
        } else {
            updateResult(result);
        }
    } catch (error) {
        showError('Network error: unable to reach the server.');
    } finally {
        showLoader(false);
    }
}

function ensureDownloadFrame() {
    let iframe = document.getElementById('downloadFrame');
    if (!iframe) {
        iframe = document.createElement('iframe');
        iframe.id = 'downloadFrame';
        iframe.name = 'downloadFrame';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
    }
    return iframe;
}

function triggerFileDownload() {
    if (downloadTriggered) {
        return;
    }

    downloadTriggered = true;
    const iframe = ensureDownloadFrame();
    iframe.src = `/api/download/file?ts=${Date.now()}`;
}

async function refreshDownloadStatus() {
    try {
        const response = await fetch('/api/progress', { cache: 'no-store' });
        const data = await response.json();
        const percentValue = Number.parseFloat(data.percent);
        const safePercent = Number.isFinite(percentValue) ? Math.min(Math.max(percentValue, 0), 100) : 0;
        const modeLabel = (data.mode || currentDownloadMode) === 'audio' ? 'audio' : 'video';

        progressFill.style.width = `${safePercent}%`;
        progressPercent.textContent = `${safePercent.toFixed(1)}%`;
        progressLabel.textContent = data.message || (
            data.status === 'processing'
                ? `Finalizing ${modeLabel} download...`
                : data.status === 'cancelling'
                    ? `Canceling ${modeLabel} download...`
                    : data.status === 'canceled'
                        ? 'Download canceled.'
                        : data.status === 'error'
                            ? 'Download failed.'
                            : `Downloading ${modeLabel}...`
        );

        if (data.status === 'complete') {
            const completedMode = (data.mode || currentDownloadMode) === 'audio' ? 'audio' : 'video';
            progressEta.textContent = 'Complete!';
            clearDownloadPolling();
            triggerFileDownload();
            setTimeout(() => {
                hideDownloadProgress();
                setDownloadControls(false);
                downloadTriggered = false;
                flashStatus(`${completedMode === 'audio' ? 'Audio' : 'Video'} download complete! Check your browser downloads.`, 3500);
            }, 1200);
            return;
        }

        if (data.status === 'canceled') {
            clearDownloadPolling();
            hideDownloadProgress();
            setDownloadControls(false);
            downloadTriggered = false;
            flashStatus('Download canceled.', 3000);
            return;
        }

        if (data.status === 'error') {
            clearDownloadPolling();
            hideDownloadProgress();
            setDownloadControls(false);
            downloadTriggered = false;
            showError(data.error || 'Download failed.', { hideResults: false });
            return;
        }

        if (data.status === 'processing') {
            progressEta.textContent = 'Finishing up...';
        } else if (data.status === 'cancelling') {
            progressEta.textContent = 'Canceling...';
        } else if (data.eta !== null && data.eta !== undefined && data.eta !== '') {
            progressEta.textContent = `ETA: ${formatDuration(data.eta)}`;
        } else {
            progressEta.textContent = 'ETA: --:--';
        }
    } catch (error) {
        console.error('Error fetching progress:', error);
    }
}

async function startNamedDownload(mode) {
    if (mode !== 'video' && mode !== 'audio') {
        showError('Unsupported download mode.', { hideResults: false });
        return;
    }

    if (!currentVideoData) {
        showError('Analyze a video before downloading.', { hideResults: false });
        return;
    }

    if (downloadInProgress) {
        showError('A download is already in progress. Cancel it first.', { hideResults: false });
        return;
    }

    const url = videoUrl.value.trim();
    if (!url) {
        showError('Please enter a valid video URL.', { hideResults: false });
        return;
    }

    clearError();
    clearDownloadPolling();
    downloadTriggered = false;
    setDownloadControls(true, mode);
    showDownloadProgress();
    progressLabel.textContent = `Starting ${mode} download...`;
    flashStatus(`Starting ${mode} download...`, 2000);

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, download_mode: mode }),
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Download failed to start.');
        }

        downloadPollInterval = setInterval(refreshDownloadStatus, 1000);
        await refreshDownloadStatus();
        if (downloadPollInterval) {
            flashStatus(result.message || `Your ${mode} download started. You can cancel it while it runs.`, 4000);
        }
    } catch (error) {
        clearDownloadPolling();
        hideDownloadProgress();
        setDownloadControls(false);
        downloadTriggered = false;
        showError(error.message || 'Unable to start download.', { hideResults: false });
    }
}

async function cancelDownload() {
    if (!downloadInProgress) {
        return;
    }

    const modeLabel = currentDownloadMode === 'audio' ? 'audio' : 'video';
    cancelDownloadBtn.disabled = true;
    progressLabel.textContent = `Canceling ${modeLabel} download...`;
    flashStatus(`Canceling ${modeLabel} download...`, 2500);

    try {
        const response = await fetch('/api/download/cancel', {
            method: 'POST',
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Unable to cancel the download.');
        }
    } catch (error) {
        cancelDownloadBtn.disabled = false;
        progressLabel.textContent = error.message || 'Unable to cancel the download.';
        flashStatus(error.message || 'Unable to cancel the download.', 3500);
        showError(error.message || 'Unable to cancel the download.', { hideResults: false, hideProgress: false });
    }
}

async function copyInfo() {
    if (!currentVideoData) {
        showError('Nothing to copy yet.', { hideResults: false });
        return;
    }

    const text = `Title: ${currentVideoData.title}\nPlatform: ${currentVideoData.platform}\nDuration: ${formatDuration(currentVideoData.duration)}\nURL: ${currentVideoData.webpage_url}`;

    try {
        await navigator.clipboard.writeText(text);
        flashStatus('Copied to clipboard!', 2500);
    } catch {
        showError('Unable to copy to clipboard.', { hideResults: false });
    }
}

async function setCookies() {
    const cookieText = cookiesInput.value.trim();
    
    if (!cookieText) {
        flashCookiesStatus('Please paste cookies JSON.', 'error');
        return;
    }
    
    try {
        const cookies = JSON.parse(cookieText);
        if (!Array.isArray(cookies)) {
            throw new Error('Cookies must be a JSON array');
        }
        
        const response = await fetch('/api/cookies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookies }),
        });
        
        if (!response.ok) {
            throw new Error(`Failed to save cookies: ${response.statusText}`);
        }
        
        cookiesInput.value = '';
        flashCookiesStatus('Cookies saved successfully! Try analyzing videos again.', 'success');
    } catch (error) {
        flashCookiesStatus(`Error: ${error.message}`, 'error');
    }
}

function flashCookiesStatus(message, type = 'success') {
    cookiesStatus.textContent = message;
    cookiesStatus.style.color = type === 'error' ? 'var(--danger)' : 'var(--success)';
    setTimeout(() => {
        cookiesStatus.textContent = '';
    }, 5000);
}

analyzeBtn.addEventListener('click', analyzeUrl);
videoUrl.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') analyzeUrl();
});
viewVideoBtn.addEventListener('click', openPreviewOrSource);
downloadVideoBtn.addEventListener('click', () => startNamedDownload('video'));
downloadAudioBtn.addEventListener('click', () => startNamedDownload('audio'));
cancelDownloadBtn.addEventListener('click', cancelDownload);
copyInfoBtn.addEventListener('click', copyInfo);
setCookiesBtn.addEventListener('click', setCookies);
thumbnailImage.addEventListener('click', openPreviewOrSource);
closePreviewBtn.addEventListener('click', closePreview);

darkModeToggle.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', nextTheme);
    darkModeToggle.textContent = nextTheme === 'dark' ? 'Light Mode' : 'Dark Mode';
});

const savedTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
darkModeToggle.textContent = savedTheme === 'dark' ? 'Light Mode' : 'Dark Mode';
