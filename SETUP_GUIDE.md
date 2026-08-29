# HostTalk Setup Guide

## Overview

HostTalk is a self-hosted, local-network messaging application with modern features including direct messages, file sharing, GIFs, link previews, and LocalSend integration.

## Requirements

- Python 3.8+
- pip (Python package manager)

## Installation

### 1. Clone/Download the Repository

```bash
cd HostTalk
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root (already included):

```env
# HostTalk Environment Variables
SERVER_PASSWORD=your_secure_password

# Optional: GIPHY API Key for GIF search (get from https://developers.giphy.com/)
GIPHY_API_KEY=your_api_key

# Logging
LOG_LEVEL=INFO
```

**Important**: Change `SERVER_PASSWORD` to a secure password before running!

## Running the Server

### Development Mode

```bash
python server.py
```

The server will start on `http://0.0.0.0:6767/` and automatically open in your browser.

### Production Mode

For production, consider using a process manager like `systemd` (Linux) or running as a Windows service.

## Accessing from Other Devices

1. Ensure all devices are on the **same WiFi network**
2. Find the server's LAN IP (shown in console on startup)
3. Other devices connect to: `http://<SERVER_IP>:6767/`
4. Enter the server password when prompted

## Features Overview

### 🔐 Password-Protected Hosting
- Server-wide password required to join
- Changeable via UI (Settings → Change Password) or `.env` file
- Bcrypt-hashed for security

### 💬 Direct Messages (DMs)
- Click any user in the user list (right sidebar) to start a DM
- Right-click user → "Open DM" or "Create DM Link"
- Password-protect DMs: Right-click user → "Set DM Password"
- DM links: Right-click user → "Create DM Link" → share the link

### 📁 File Sharing
- Click the **paperclip icon** next to the message input
- Select any file (images, PDFs, documents, archives)
- Files >20MB are **auto-compressed**:
  - Images: Quality reduced automatically
  - Other files: Gzip compressed
- Download files by clicking the download link in chat

### 🎨 User Colors
- Open Settings (⋮ button) → "Your Color" section
- Click any color from the 20-color grid
- Or use the custom color picker + "Use Custom"
- Colors are unique per user (no duplicates)

### ↩️ Quoting Replies
- Hover any message → click "↩️ Reply"
- Type your reply → press Enter
- Quoted message appears above your reply

### 🔗 Link Previews
- Paste any URL in chat
- Automatic OpenGraph preview (title, description, image)
- Works for YouTube, GitHub, news sites, etc.

### 🎭 GIFs & Stickers
- Settings → "Stickers & GIFs"
- Search GIFs (powered by GIPHY)
- Click to send instantly

### 📋 Nickname Changes
- Settings → "Profile" → enter new nickname → "Change"
- 1-hour cooldown between changes
- Host can view full history: Settings → "View Nickname History"

### 📊 Server Logs (Host Only)
- Settings → "View Server Logs"
- Structured logging with timestamps
- Log file: `%APPDATA%/HostTalk/hosttalk.log`

### 📡 LocalSend Integration (LAN File Transfer)
- Settings → "LocalSend" → "Scan for Devices"
- Discovers other LocalSend-compatible devices on LAN
- Click "Connect" next to a device
- Use "Send File via LocalSend" to transfer files directly
- Implements LocalSend v2 REST API

## Configuration

### Change Server Password

**Via UI** (Host only):
1. Settings → "Change Password"
2. Enter old and new password

**Via .env file**:
```env
SERVER_PASSWORD=new_secure_password
```

### GIPHY API Key (Optional)

For better GIF search, add your API key:
```env
GIPHY_API_KEY=your_giphy_api_key
```
Get a free key at: https://developers.giphy.com/

### Port Configuration

Default port: **6767**

To change, edit `server.py`:
```python
s.run(app, host="0.0.0.0", port=YOUR_PORT, debug=False)
```

## Network Requirements

- **Port 6767** (TCP) - Main chat server
- **Port 53317** (UDP) - LocalSend multicast discovery
- All devices must be on same subnet/LAN

## Troubleshooting

### "Failed to fetch data" in Invite popup
- Server couldn't detect WiFi SSID
- Ensure running with network permissions

### Can't connect from other devices
1. Check firewall allows port 6767
2. Verify same WiFi network
3. Try `http://<IP>:6767/` (not localhost)

### LocalSend not discovering devices
- Ensure multicast not blocked by router
- Try HTTP discovery fallback (auto-enabled)
- Check devices run LocalSend or HostTalk

### GIFs not loading
- Check internet connection (GIPHY API)
- Add GIPHY_API_KEY to .env for higher limits

## File Structure

```
HostTalk/
├── server.py              # Main backend
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── SETUP_GUIDE.md        # This file
├── IMPLEMENTATION_PLAN.md # Technical docs
├── static/
│   ├── chat.js           # Frontend logic
│   ├── options.js        # Theme/settings
│   ├── rightclick.js     # Context menus
│   ├── customization.js  # UI customization
│   ├── main.css          # Styles
│   ├── responsive.css    # Mobile styles
│   ├── lib/
│   │   ├── compressor.min.js
│   │   └── fflate.min.js
│   └── [audio/icon files]
└── templates/
    └── index.html        # Main UI template
```

## Data Storage

- **Messages**: In-memory (last 10 in group chat)
- **DMs**: In-memory per user pair
- **Logs**: File-based (`hosttalk.log`)
- **User preferences**: Browser localStorage
- **Nickname history**: Server memory (host only)

## Security Notes

- Passwords bcrypt-hashed (never stored plaintext)
- DM passwords also bcrypt-hashed
- No persistent message storage by default
- LocalSend uses HTTP (add HTTPS for production)
- Server password required for all connections

## Customization

### Themes
Settings → "Theme" → choose iOS 6, 16, or 26 style

### Dark/Light Mode
Settings → "Appearence" → Dark/Light

### Border Radius
Settings → "Border radius" slider

### Placeholder Text
Settings → "Placeholder" → custom text

## License

MIT License - See LICENSE file

## Support

For issues, check:
1. Console logs (F12 → Console)
2. Server terminal output
3. Log file: `%APPDATA%/HostTalk/hosttalk.log`

---

*HostTalk v1.0 - Local Network Messaging*