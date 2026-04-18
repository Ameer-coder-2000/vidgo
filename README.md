# Universal Video Analyzer

A simple full-stack web app for analyzing video URLs from platforms like YouTube, Instagram, Facebook, and TikTok.

## Features

- Detects the video platform from a pasted URL
- Extracts title, thumbnail, duration, uploader, and available formats
- Displays a clean preview card with video details
- Lets you preview the video in-app or open the source page
- Includes a background download button with cancel support
- Shows a loading animation while analyzing
- Supports copy-to-clipboard for video information
- Includes a dark mode toggle

## Project Structure

- `app.py` - Flask backend and API routes
- `templates/index.html` - Frontend HTML page
- `static/style.css` - Frontend styling
- `static/script.js` - Frontend logic and UI interaction
- `requirements.txt` - Python dependency list

## Requirements

- Python 3.10+ or newer
- `pip` package manager

## Install and run locally

1. Open a terminal in the project folder.
2. Create a virtual environment (recommended):

```bash
python -m venv venv
```

3. Activate the virtual environment:

- Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

- Windows CMD:

```cmd
venv\Scripts\activate.bat
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Start the Flask app:

```bash
python app.py
```

6. Open your browser at `http://127.0.0.1:5000`

## Usage

- Paste a video URL into the input field.
- Click `Analyze`.
- Select a desired format and click `View Video` or `Download`.
- If you start a download, you can cancel it from the progress panel while it runs.
- Use `Copy Info` to copy metadata to the clipboard.

## Notes

- The download feature uses `yt-dlp` to fetch the video file in the background, and you can cancel it before it finishes.
- Some platforms may require additional support or network access.
- For unsupported URLs, the app shows a friendly error.
