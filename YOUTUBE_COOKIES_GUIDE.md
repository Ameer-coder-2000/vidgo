# How to Export and Use YouTube Cookies

YouTube now requires authentication to prevent bot abuse. To use this app with YouTube videos, you need to provide your YouTube cookies.

## Quick Guide

### Step 1: Export Cookies from Your Browser

#### Option A: Using Browser Extension (Easiest)
1. Install one of these extensions:
   - **Chrome/Edge:** [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndtbojmajojkglhhiblahjplbkd)
   - **Firefox:** [cookie-txt](https://addons.mozilla.org/firefox/addon/cookie-txt/) or [Get cookies.txt LOCALLY](https://addons.mozilla.org/firefox/addon/get-cookiestxt-locally/)

2. Go to https://youtube.com and make sure you're **logged in**

3. Click the extension icon and select "Export cookies as JSON" (or similar option)

4. Copy the exported cookies

#### Option B: Manual Export from DevTools
1. Go to https://youtube.com while logged in
2. Open DevTools (F12 or right-click → Inspect)
3. Go to Application → Cookies → youtube.com
4. You'll see your cookies - copy them and convert to JSON format

### Step 2: Format the Cookies

The cookies should be a JSON array. Example:
```json
[
  {
    "domain": ".youtube.com",
    "name": "VISITOR_INFO1_LIVE",
    "value": "YOUR_VALUE_HERE",
    "path": "/",
    "secure": true,
    "httpOnly": true
  },
  {
    "domain": ".youtube.com", 
    "name": "CONSENT",
    "value": "YES+1",
    "path": "/",
    "secure": true,
    "httpOnly": true
  }
]
```

**Most important cookies needed:**
- `VISITOR_INFO1_LIVE`
- `CONSENT`
- `LOGIN_INFO` (if available)
- `SECURE_LOGIN_BULK` (if available)

### Step 3: Add Cookies to the App

1. **Local Testing:** Run the app and open it in browser
2. **Deployed (Render):** Visit your deployed app URL
3. Click the **"🔐 YouTube Authentication (Optional...)"** section to expand it
4. Paste your cookies JSON in the text area
5. Click **"Save Cookies"**
6. A success message should appear
7. Now try analyzing YouTube videos!

## Troubleshooting

### Still getting "Sign in to confirm you're not a bot" error?
- Make sure you're logged into YouTube when exporting cookies
- Try exporting fresh cookies (the old ones may have expired)
- Check that the JSON format is valid (use a JSON validator)
- Wait a few minutes after saving before trying again

### Cookies not working?
- Try updating to the latest version of the app (check GitHub)
- Make sure you have the most essential cookies: `VISITOR_INFO1_LIVE` and `CONSENT`
- Try with a different browser's cookies

### The extension won't export properly?
- Try a different browser
- Use DevTools method (Option B above)
- Make sure you're actually logged into YouTube

## Security Note

Your cookies are stored **only in memory** on the server and are **never saved to disk or logs**. When the server restarts (or in this case, you refresh in Render), the cookies are cleared and you'll need to provide them again.

**Never share your cookies with anyone** - they contain authentication information for your YouTube account.

## Need Help?

- Check the [yt-dlp FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- See [yt-dlp Extractor Docs](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
