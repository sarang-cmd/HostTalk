# HostTalk Feature Expansion & LocalSend Integration Plan

> Superseded. This is the original plan, kept for context. `README.md` and `CHANGELOG.md`
> describe the build as it ships. Where this file and the code disagree, the code wins.

**Session ID:** ses_fbd39fb86ffenvrEY72lbjYlj3
**Last Updated:** August 27, 2026

---

## 1. Project Overview & Tech Stack Analysis

### Existing Architecture
HostTalk is a lightweight, self-hosted, local-network real-time messaging system built on:
- **Backend:** Python, Flask, Flask-SocketIO, eventlet, bcrypt, python-dotenv, logging.
- **Frontend:** HTML5, CSS3 (with custom iOS-inspired theme options), JavaScript, Socket.IO client, local storage.
- **System Integration:** pystray, PIL (Pillow), kernel32/user32 via ctypes (Windows-only tray & console control).

---

## 2. Refined Feature Specification & Requirements

### A. Security & Access Control
1. **Server Password-Protected Hosting**
   - Restrict access to the chat.
   - Password stored and loaded from `.env` via `SERVER_PASSWORD`.
   - Salt and hash passwords using `bcrypt`.
   - Host can change or reset the password via the UI, falling back to direct `.env` edits.
   - Prompt users for the password upon first connection, saving to `localStorage` for future auto-connection.

2. **Unified Group Chat**
   - Retain the current unified group chat (`mainchat` system) as-is. No participant limits or admins for this central room.

### B. Messaging & Media Enhancements
1. **Image and File Sending (Max 20MB)**
   - Allow uploading images (PNG, JPG, GIF) and documents (PDF, etc.) up to 20MB.
   - Cache files temporarily in the browser using `IndexedDB` or `localStorage`.
   - Automatically compress/quality-decrease images/files if they exceed 20MB using client-side libraries (like `compressorjs` and `fflate`) to fit the size limit before dispatch.

2. **Direct Messages (DMs)**
   - Simple, private chats between two users.
   - Messages stored temporarily in server memory (no persistent storage).
   - Display a "DM" button next to users in the user list.
   - Support shareable **DM Links** and optional **DM Passwords** to protect private conversations.

3. **Stickers & GIFs**
   - Allow searching and sending GIFs using a free, open-source API (e.g., Tenor API or GIPHY Public Beta).

4. **Different Colors for Different Users**
   - Predefined grid of 20 distinct, high-contrast colors.
   - No repetition of colors among active users.
   - User customization option via a color-picker grid in the settings.

5. **Quoting Replies**
   - Allow users to quote and reply to specific messages.
   - Display quoted messages elegantly inside the chat UI bubbles.

6. **Rich Link Previews**
   - Extract title, description, and preview image from links sent in the chat.
   - Done securely on the backend (e.g., using `BeautifulSoup` or `urllib` to scrape metadata) to avoid CORS issues.

### C. System & Moderation
1. **Changing Nicknames with Cooldown & Logging**
   - Cooldown period of 1 hour per nickname change.
   - Log all nickname changes securely on the server (`logs/nickname_changes.log`).

2. **Cleaner & Restrictive Host Logs**
   - Standardized log levels (`INFO`, `WARNING`, `ERROR`) using Python's `logging` library.
   - Secure host-only log viewer exposed in the UI.

### D. LocalSend Integration (Enabled by Default)
1. **No Installation Required**
   - Implemented within HostTalk itself to interoperate natively with LocalSend clients.
2. **Device Discovery**
   - Handle LocalSend multicast UDP notifications (`224.0.0.167:53317`) in Python to identify devices on the local network.
   - Support HTTP-based scans of local IPs as a discovery fallback.
3. **File Transfer Protocol**
   - Implement LocalSend's `/api/localsend/v2/register`, `/prepare-upload`, and `/upload` endpoints to seamlessly exchange files with LocalSend.
   - Enable HTTPS with self-signed certificate generation.

---

## 3. Implementation Checklist & Phase Ordering

1. **Phase 1: Server Authentication & Access Control** (Password-protected hosting, bcrypt, `.env`, connection gating)
2. **Phase 2: User Visual Customizations** (Distinct user colors, color grid picker)
3. **Phase 3: File / Image Uploads & Compression** (20MB limit, auto-compression, browser cache storage)
4. **Phase 4: Message Quoting & Link Previews** (Quoted reply attachments, metadata scraper)
5. **Phase 5: Direct Messages (DMs) & Secure DMs** (DM threads, temporary DM arrays, DM links/passwords)
6. **Phase 6: Stickers, GIFs, Nickname Cooldowns & Cleaner Logs** (Tenor/Giphy API, host-only log view)
7. **Phase 7: LocalSend LAN Interoperability** (UDP Multicast responder, HTTPS self-signed, upload API endpoints)
