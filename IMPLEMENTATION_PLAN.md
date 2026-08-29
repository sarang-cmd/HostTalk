# HostTalk Implementation Plan

## Project Overview
HostTalk is a self-hosted, local-network messaging system built with Python (Flask + Socket.IO) and vanilla JavaScript frontend.

## Conversation Summary

### Initial Request
The user requested adding the following features to HostTalk:
- Image sending
- Direct Messages (DMs)
- Separate group chats
- Different colors for different users
- Changing nicknames (with logging)
- Cleaner logs
- DM links
- DM passwords
- Quoting replies
- Stickers and GIFs
- Links (preview and handling)
- LocalSend LAN integration

### Clarifications Provided

1. **Image/File Handling**:
   - Store in browser cache (localStorage/IndexedDB)
   - Size limit: 20MB
   - Auto-compress if over limit
   - No option to disable compression

2. **Direct Messages**:
   - Keep simple, temporary storage
   - No changes to existing unified group chat
   - Add password to host the server itself

3. **Group Chats**:
   - Keep existing unified group chat
   - No admins
   - Participant limit: 20 for new group chats

4. **Colors**:
   - User customizable
   - Predefined grid of colors (no repetition)

5. **Nicknames**:
   - Cooldown: 1 hour
   - No approval required
   - Logging for host only

6. **Logs**:
   - Cleaner logs with levels
   - Host-only access

7. **GIFs**:
   - Free API (GIPHY/Tenor)
   - Completely free/open source

8. **LocalSend**:
   - No installation required
   - Enabled by default

9. **Password**:
   - Store in .env file
   - Also changeable via UI
   - Hash passwords with bcrypt
   - Allow password reset

---

## Implementation Priority Order

### Phase 1: Security & Core Features (High Priority)
1. **Password-Protected Hosting** - Server-wide password with .env + UI
2. **Image/File Compression on Upload** - Auto-compress to 20MB limit
3. **Direct Messages (DMs)** - Private messaging between users

### Phase 2: UX Improvements (Medium Priority)
4. **User Colors** - Customizable with predefined grid
5. **Quoting Replies** - Reply to specific messages
6. **Link Previews** - Rich previews for URLs

### Phase 3: Enhanced Features (Low Priority)
7. **Cleaner Logs** - Structured logging (host-only)
8. **Stickers & GIFs** - Free API integration
9. **DM Links** - Shareable DM invitations
10. **DM Passwords** - Password-protect DM threads
11. **Nickname Changes** - With cooldown and logging
12. **LocalSend Integration** - LAN file/messaging

---

## Technical Architecture

### Backend (server.py)
- **Framework**: Flask + Flask-SocketIO
- **Authentication**: bcrypt-hashed passwords
- **Storage**: In-memory (mainchat, users, dms)
- **Logging**: Python logging module (file-based)
- **Environment**: python-dotenv for .env

### Frontend (static/)
- **chat.js**: Core messaging logic
- **options.js**: Theme/settings management
- **rightclick.js**: Context menus
- **index.html**: Main UI template
- **main.css**: Styling with CSS variables

### Key Data Structures
```python
mainchat = []  # Last 10 messages
users = {}  # sid -> {name, color, last_nick_change}
dms = {}  # user1 -> user2 -> [messages]
server_password = ""  # bcrypt hash
```

---

## Detailed Feature Specifications

### 1. Password-Protected Hosting
- **Backend**:
  - `SERVER_PASSWORD` in .env (bcrypt hashed)
  - Verify on `join` event
  - `/api/change-password` endpoint
  - Fallback to .env if UI fails
- **Frontend**:
  - Password prompt on connection
  - "Change Password" in settings (host-only)
  - "Forgot Password" reset option

### 2. File Compression (20MB limit)
- **Images**: compressorjs (quality auto-adjust)
- **Files**: fflate for compression
- **UI**: Preview original vs compressed size
- **Trigger**: Only if > 20MB

### 3. Direct Messages
- **Backend**: `dm` event, `dms` dict
- **Frontend**: DM button on user list, separate UI
- **Storage**: Temporary in-memory

### 4. User Colors
- **Grid**: 20 predefined distinct colors
- **Assignment**: Unique per user
- **Customization**: Color picker in settings
- **Persistence**: localStorage

### 5. Quoting Replies
- **Backend**: `reply` event with message ID
- **Frontend**: Reply button on messages
- **UI**: Quoted message preview

### 6. Link Previews
- **Backend**: `/fetch-link-meta` endpoint
- **Libraries**: requests + BeautifulSoup
- **Frontend**: Auto-detect URLs, fetch preview

### 7. Cleaner Logs
- **Levels**: INFO, WARNING, ERROR
- **Output**: hosttalk.log (host-only)
- **UI**: "View Logs" in settings (host-only)

### 8. Stickers & GIFs
- **API**: GIPHY/Tenor free tier
- **UI**: GIF picker in chat input
- **Search**: Real-time search

### 9. DM Links
- **Backend**: `/generate-dm-link`, `/join-dm`
- **Frontend**: "Copy Link" in DM UI

### 10. DM Passwords
- **Backend**: `set-dm-password`, `join-dm` with password
- **Frontend**: "Set Password" in DM UI

### 11. Nickname Changes
- **Cooldown**: 1 hour
- **Logging**: host-only log file
- **UI**: Change nickname in settings

### 12. LocalSend Integration
- **Discovery**: UDP multicast + HTTP fallback
- **Transfer**: REST API (/prepare-upload, /upload)
- **Security**: Self-signed certs, optional PIN
- **Default**: Enabled

---

## Current Implementation Status

### Completed (from conversation)
- ✅ Added `bcrypt` and `dotenv` to requirements.txt
- ✅ Created `.env` file with SERVER_PASSWORD
- ✅ Modified server.py to load env vars
- ✅ Added password hashing on startup
- ✅ Added logging configuration
- ✅ Added password verification in `join` event
- ✅ Added `/api/change-password` endpoint

### In Progress
- 🔄 File compression frontend (chat.js)
- 🔄 DM functionality

### Pending
- ⏳ User colors
- ⏳ Quoting replies
- ⏳ Link previews
- ⏳ Cleaner logs UI
- ⏳ Stickers/GIFs
- ⏳ DM links
- ⏳ DM passwords
- ⏳ Nickname changes
- ⏳ LocalSend integration

---

## File Structure After Implementation

```
HostTalk/
├── server.py              # Main backend (extended)
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── IMPLEMENTATION_PLAN.md # This file
├── static/
│   ├── chat.js           # Core messaging (extended)
│   ├── options.js        # Settings/themes
│   ├── rightclick.js     # Context menus
│   ├── compressorjs/     # Image compression
│   ├── fflate/           # File compression
│   ├── main.css          # Styles
│   └── responsive.css    # Mobile styles
├── templates/
│   └── index.html        # Main UI (extended)
└── Assets/               # Static assets
```

---

## Dependencies Added

### Python (requirements.txt)
```
Flask
Flask-SocketIO
eventlet
pystray
Pillow
bcrypt
dotenv
```

### Frontend (to be added)
- compressorjs (image compression)
- fflate (file compression)

---

## Testing Checklist

### Password Protection
- [ ] Connection fails with wrong password
- [ ] Connection succeeds with correct password
- [ ] Password change via UI works
- [ ] Password change updates .env
- [ ] Forgot password reset works

### File Compression
- [ ] Files < 20MB sent without compression
- [ ] Files > 20MB auto-compressed
- [ ] Preview shows original vs compressed
- [ ] All file types handled

### Direct Messages
- [ ] DM button appears on user list
- [ ] DM thread opens correctly
- [ ] Messages only visible to participants
- [ ] Unread indicators work

### Other Features
- [ ] Each feature tested individually
- [ ] Cross-browser compatibility
- [ ] Mobile responsiveness
- [ ] Error handling

---

## Notes for Future Development

1. **Persistence**: Current implementation uses in-memory storage. Consider Redis or SQLite for persistence.
2. **Scalability**: In-memory storage limits horizontal scaling. Plan for session affinity or shared storage.
3. **Security**: Consider adding rate limiting, CSRF protection, and HTTPS enforcement.
4. **Mobile**: Ensure all new features work on mobile browsers.
5. **Accessibility**: Maintain WCAG compliance for new UI elements.

---

*Generated from conversation on 2026-08-28*
*HostTalk v1.0 - Local Network Messaging*