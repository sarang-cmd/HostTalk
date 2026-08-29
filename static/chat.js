const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

window.addEventListener("DOMContentLoaded", function() {
    chat = document.getElementById('chat');
    let notificationA = new Audio(`static/recieved.mp3`);
    let notificationB = new Audio(`static/sent.mp3`);
    document.querySelectorAll(`[splash="icon"]`).forEach(llkv => {
        llkv.addEventListener("animationend", function() {
            llkv.closest("splash").style.display = "none";
        });
    });
    window.sdihkid = io();
    
    // Client-side users object to track connected users
    window.users = {};
    window.userColors = {};
    
    let usrahh = localStorage.getItem('userID');
    if (!usrahh) {
        usrahh = prompt("Enter username to continue");
        localStorage.setItem("userID", usrahh);
    }
    
    // Make usrahh globally accessible and updatable
    window.usrahh = usrahh;
    
    sdihkid.on('connect', function() {
        // Check if server requires password
        const savedPassword = localStorage.getItem('serverPassword');
        if (savedPassword) {
            sdihkid.emit('join', {name: window.usrahh, password: savedPassword});
        } else {
            sdihkid.emit('join', {name: window.usrahh});
        }
    });

    // Track connected users
    sdihkid.on("user_joined", data => {
        window.users[data.name] = { color: data.color || '#888' };
        window.userColors[data.name] = data.color || '#888';
        updateUserList();
    });

    sdihkid.on("user_left", data => {
        delete window.users[data.name];
        delete window.userColors[data.name];
        updateUserList();
    });

    sdihkid.on('auth_error', function(data) {
        alert(data.message);
        localStorage.removeItem('serverPassword');
        location.reload();
    });

    const orgAud = this.window.Audio;
    window.Audio = function(...args) {
        const audio = new orgAud(...args);
        audio.volume = 0.3;
        return audio;
    };

    sdihkid.on("mainchat", d => {
        if (currentDM) return; // Don't show group messages in DM view
        
        const each$$cov = document.createElement("div");
        const each$$msg = document.createElement("p");
        
        // Handle quoted message
        if (d.quoted) {
            renderQuotedMessage(d.quoted, each$$msg);
        }
        
        if (d.type === "file") {
            renderFileMessage(d, each$$msg, each$$cov);
        } else if (d.type === "image") {
            renderImageMessage(d, each$$msg, each$$cov);
        } else {
            each$$msg.innerHTML = `${d.msg}`;
        }
        
        if (d.msg && d.msg.length >= 31) {
            each$$msg.setAttribute('large', '2');
            each$$cov.setAttribute('large', '2c');
        }
        if (d.name == window.usrahh) {
            each$$msg.setAttribute('mine', 'yesvro');
            each$$cov.setAttribute('mine', 'yescover');
            each$$cov.setAttribute('setmarg', '02');
            
            // Add reply button for own messages
            addReplyButton(each$$cov, d);
        } else {
            let a = document.createElement('p');
            const userColor = window.userColors[d.name] || '#888';
            a.innerHTML = `<span style="color: ${userColor}; font-weight: 600;">${escapeHtml(d.name)}</span>`;
            a.setAttribute('tag', 'user');
            each$$msg.setAttribute('mine', 'fuhnaw');
            each$$cov.setAttribute('mine', 'nocover');
            each$$cov.appendChild(a);
        }
        each$$cov.setAttribute("bubble", "cover");
        chat.appendChild(each$$cov);
        each$$cov.appendChild(each$$msg);
        window.scrollTo(0, document.body.scrollHeight);
        notificationA.play();
        
        // Process links for previews
        if (d.msg && typeof d.msg === 'string') {
            processMessageForLinks(d.msg);
        }
    });

    function renderFileMessage(d, msgEl, covEl) {
        const fileSize = formatFileSize(d.size);
        const fileIcon = getFileIcon(d.name);
        msgEl.innerHTML = `
            <div class="file-message">
                <span class="file-icon">${fileIcon}</span>
                <div class="file-info">
                    <span class="file-name">${escapeHtml(d.name)}</span>
                    <span class="file-size">${fileSize}</span>
                </div>
                <a href="${d.url}" download="${escapeHtml(d.name)}" class="file-download">Download</a>
            </div>
        `;
if (d.name == window.usrahh) {
            msgEl.setAttribute('mine', 'yesvro');
        }
    }
    
    function renderImageMessage(d, msgEl, covEl) {
        msgEl.innerHTML = `
            <div class="image-message">
                <img src="${d.url}" alt="${escapeHtml(d.name)}" class="chat-image" onclick="openImageModal('${d.url}')">
                <span class="image-name">${escapeHtml(d.name)}</span>
            </div>
        `;
        if (d.name == window.usrahh) {
            msgEl.setAttribute('mine', 'yesvro');
        }
    }

    function getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            'pdf': '📄', 'txt': '📝', 'doc': '📄', 'docx': '📄',
            'zip': '📦', 'rar': '📦', '7z': '📦',
            'mp3': '🎵', 'wav': '🎵', 'ogg': '🎵',
            'mp4': '🎬', 'webm': '🎬', 'mov': '🎬',
            'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️',
        };
        return icons[ext] || '📎';
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderQuotedMessage(quoted, msgEl) {
        const quoteEl = document.createElement('div');
        quoteEl.className = 'quoted-message';
        quoteEl.style.cssText = `
            border-left: 3px solid var(--accent);
            padding-left: 12px;
            margin-bottom: 8px;
            background: var(--bg-quote);
            border-radius: 4px;
            font-size: 0.85em;
        `;
        
        const quotedName = quoted.name || 'Unknown';
        const quotedColor = userColors[quotedName] || '#888';
        const quotedContent = quoted.msg || '';
        
        quoteEl.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span style="color: ${quotedColor}; font-weight: 600; font-size: 0.8em;">${escapeHtml(quotedName)}</span>
                <span style="color: var(--accent); font-size: 0.7em;">REPLYING TO</span>
            </div>
            <div style="color: var(--text-muted); white-space: pre-wrap;">${escapeHtml(quotedContent.substring(0, 100))}${quotedContent.length > 100 ? '...' : ''}</div>
        `;
        msgEl.prepend(quoteEl);
    }

    function addReplyButton(covEl, message) {
        const replyBtn = document.createElement('button');
        replyBtn.innerHTML = '↩️ Reply';
        replyBtn.style.cssText = `
            margin-top: 4px; padding: 4px 8px; font-size: 0.7em;
            background: var(--accent); color: white; border: none;
            border-radius: 4px; cursor: pointer; opacity: 0.7;
            transition: opacity 0.2s;
        `;
        replyBtn.onmouseenter = () => replyBtn.style.opacity = '1';
        replyBtn.onmouseleave = () => replyBtn.style.opacity = '0.7';
        replyBtn.onclick = (e) => {
            e.stopPropagation();
            startReply(message);
        };
        covEl.appendChild(replyBtn);
    }

    let replyingTo = null;

    function startReply(message) {
        replyingTo = message;
        const inp = document.querySelector('[dih="yo"]');
        inp.placeholder = `Replying to ${message.name}...`;
        inp.focus();
        
        // Show cancel reply button
        showCancelReply();
    }

    function showCancelReply() {
        const existing = document.getElementById('cancel-reply');
        if (existing) existing.remove();
        
        const cancelBtn = document.createElement('button');
        cancelBtn.id = 'cancel-reply';
        cancelBtn.innerHTML = '✕ Cancel reply';
        cancelBtn.style.cssText = `
            margin-left: 8px; padding: 4px 8px; font-size: 0.7em;
            background: var(--bg-danger); color: var(--text-danger);
            border: 1px solid var(--border-danger); border-radius: 4px;
            cursor: pointer;
        `;
        cancelBtn.onclick = cancelReply;
        
        const inputContainer = document.querySelector('[oc="p"]');
        inputContainer.appendChild(cancelBtn);
    }

    function cancelReply() {
        replyingTo = null;
        const inp = document.querySelector('[dih="yo"]');
        inp.placeholder = inp.getAttribute('data-original-placeholder') || '';
        
        const cancelBtn = document.getElementById('cancel-reply');
        if (cancelBtn) cancelBtn.remove();
    }

    // Link preview functionality
    function extractUrls(text) {
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return text.match(urlRegex) || [];
    }

    function fetchLinkPreview(url) {
        sdihkid.emit('fetch_link_preview', {url: url});
    }

    sdihkid.on("link_preview", data => {
        if (data.error) return;
        
        // Find messages containing this URL and update them
        const messages = chat.querySelectorAll('[bubble="cover"]');
        messages.forEach(msg => {
            const textContent = msg.textContent;
            if (textContent.includes(data.url)) {
                addLinkPreview(msg, data);
            }
        });
    });

    function addLinkPreview(msgEl, preview) {
        // Check if preview already exists
        if (msgEl.querySelector('.link-preview')) return;
        
        const previewEl = document.createElement('div');
        previewEl.className = 'link-preview';
        previewEl.style.cssText = `
            margin-top: 8px; padding: 12px; background: var(--bg-card);
            border: 1px solid var(--border); border-radius: 8px;
            display: flex; gap: 12px; max-width: 100%;
        `;
        
        let imageHtml = '';
        if (preview.image) {
            imageHtml = `<img src="${preview.image}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 4px; flex-shrink: 0;">`;
        }
        
        previewEl.innerHTML = `
            ${imageHtml}
            <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 600; color: var(--text); margin-bottom: 4px;">${escapeHtml(preview.title || preview.url)}</div>
                <div style="color: var(--text-muted); font-size: 0.85em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(preview.description || '')}</div>
                <div style="color: var(--accent); font-size: 0.75em; margin-top: 4px;">${escapeHtml(new URL(preview.url).hostname)}</div>
            </div>
        `;
        
        msgEl.appendChild(previewEl);
    }

    // Auto-detect URLs in messages and fetch previews
    function processMessageForLinks(messageText) {
        const urls = extractUrls(messageText);
        urls.forEach(url => {
            // Debounce to avoid too many requests
            setTimeout(() => fetchLinkPreview(url), 500);
        });
    }

    window.sendingmyahh = async function() {
        const inp = document.querySelector('[dih="yo"]');
        const fileInput = document.getElementById("file-upload");
        
        if (inp.value.trim() !== "") {
            const messageData = {
                type: "text",
                content: inp.value
            };
            
            if (currentDM) {
                sdihkid.emit("dm", {
                    to: currentDM,
                    msg: inp.value,
                    type: "text"
                });
            } else if (replyingTo) {
                // Send quote reply
                sdihkid.emit("quote_reply", {
                    quoted_msg_id: id(replyingTo),
                    msg: inp.value,
                    type: "text"
                });
                cancelReply();
            } else {
                sdihkid.emit("mainchat", messageData);
            }
            
            inp.value = "";
            notificationB.play();
            window.scrollTo(0, document.body.scrollHeight);
        }
        
        if (fileInput.files.length > 0) {
            await handleFileUpload(fileInput.files[0]);
            fileInput.value = "";
        }
    };

    async function handleFileUpload(file) {
        if (file.size <= MAX_FILE_SIZE) {
            // File is under limit, send directly
            await uploadFile(file);
            return;
        }

        // File is over limit, compress it
        const compressedFile = await compressFile(file);
        await uploadFile(compressedFile);
    }

    async function compressFile(file) {
        const isImage = file.type.startsWith('image/');
        
        if (isImage) {
            return new Promise((resolve, reject) => {
                new Compressor(file, {
                    quality: 0.8,
                    maxWidth: 1920,
                    maxHeight: 1080,
                    mimeType: file.type,
                    success(result) {
                        if (result.size <= MAX_FILE_SIZE) {
                            resolve(result);
                        } else {
                            // Try lower quality
                            new Compressor(file, {
                                quality: 0.6,
                                maxWidth: 1600,
                                maxHeight: 900,
                                mimeType: 'image/jpeg',
                                success(result2) {
                                    resolve(result2);
                                },
                                error(err) {
                                    reject(err);
                                }
                            });
                        }
                    },
                    error(err) {
                        reject(err);
                    }
                });
            });
        } else {
            // For non-image files, use fflate to compress
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = async function(e) {
                    try {
                        const data = new Uint8Array(e.target.result);
                        const compressed = fflate.gzipSync(data);
                        const compressedBlob = new Blob([compressed], { type: 'application/gzip' });
                        const compressedFile = new File([compressedBlob], file.name + '.gz', { type: 'application/gzip' });
                        
                        if (compressedFile.size <= MAX_FILE_SIZE) {
                            resolve(compressedFile);
                        } else {
                            // Still too large, send original with warning
                            resolve(file);
                        }
                    } catch (err) {
                        reject(err);
                    }
                };
                reader.onerror = () => reject(new Error('Failed to read file'));
                reader.readAsArrayBuffer(file);
            });
        }
    }

    async function uploadFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = function(e) {
                const base64 = e.target.result;
                const isImage = file.type.startsWith('image/');
                
                sdihkid.emit("mainchat", {
                    type: isImage ? "image" : "file",
                    name: file.name,
                    size: file.size,
                    data: base64,
                    mimeType: file.type
                });
                resolve();
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsDataURL(file);
        });
    }

    // DM state
    let currentDM = null;
    let dmHistory = {};
    let dmUsers = new Set();
    let userColors = {};
    const mainchat = []; // Store group messages

    sdihkid.on("dm", d => {
        const isCurrentDM = currentDM && (d.from === currentDM || d.to === currentDM);
        if (isCurrentDM) {
            renderDMMessage(d);
            window.scrollTo(0, document.body.scrollHeight);
        } else {
            showDMNotification(d.from);
        }
        notificationA.play();
    });

    sdihkid.on("dm_history", data => {
        dmHistory[data.with] = data.messages;
        if (currentDM === data.with) {
            renderDMHistory(data.messages);
        }
    });

    sdihkid.on("dm_error", data => {
        alert(data.message);
    });

    // User join/leave events
    sdihkid.on("user_joined", data => {
        if (data.name !== window.usrahh) {
            // Store user color
            window.userColors[data.name] = data.color;
            updateUserList();
        }
    });

    sdihkid.on("user_left", data => {
        delete window.userColors[data.name];
        updateUserList();
    });

    sdihkid.on("user_color_changed", data => {
        window.userColors[data.name] = data.color;
        updateUserList();
    });

    sdihkid.on("color_error", data => {
        alert(data.message);
    });

    function renderDMMessage(d) {
        const each$$cov = document.createElement("div");
        const each$$msg = document.createElement("p");
        const isSent = d.from === window.usrahh;
        
        if (d.type === "file") {
            renderFileMessage(d, each$$msg, each$$cov);
        } else if (d.type === "image") {
            renderImageMessage(d, each$$msg, each$$cov);
        } else {
            each$$msg.innerHTML = `${d.msg}`;
        }
        
        if (d.msg && d.msg.length >= 31) {
            each$$msg.setAttribute('large', '2');
            each$$cov.setAttribute('large', '2c');
        }
        if (isSent) {
            each$$msg.setAttribute('mine', 'yesvro');
            each$$cov.setAttribute('mine', 'yescover');
            each$$cov.setAttribute('setmarg', '02');
        } else {
            let a = document.createElement('p');
            a.innerHTML = d.from;
            a.setAttribute('tag', 'user');
            each$$msg.setAttribute('mine', 'fuhnaw');
            each$$cov.setAttribute('mine', 'nocover');
            each$$cov.appendChild(a);
        }
        each$$cov.setAttribute("bubble", "cover");
        chat.appendChild(each$$cov);
        each$$cov.appendChild(each$$msg);
    }

    function renderDMHistory(messages) {
        chat.innerHTML = '';
        messages.forEach(msg => renderDMMessage(msg));
    }

    function showDMNotification(from) {
        const userList = document.getElementById('user-list');
        if (userList) {
            const userItem = userList.querySelector(`[data-user="${from}"]`);
            if (userItem) {
                let badge = userItem.querySelector('.dm-badge');
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'dm-badge';
                    userItem.appendChild(badge);
                }
                badge.textContent = '•';
                badge.style.display = 'inline';
            }
        }
    }

    window.openDM = function(username) {
        if (username === window.usrahh) return;
        
        // Check for DM password first
        sdihkid.emit('open_dm', {with: username}, (response) => {
            if (response.required) {
                // Show password prompt
                const password = prompt(`This DM with ${username} is password protected. Enter password:`);
                if (!password) return;
                
                // Verify password
                sdihkid.emit('check_dm_password', {with: username, password: password}, (verifyResponse) => {
                    if (verifyResponse.valid) {
                        openDMInternal(username);
                    } else {
                        alert('Incorrect password');
                    }
                });
            } else {
                openDMInternal(username);
            }
        });
    };

    function openDMInternal(username) {
        if (username === window.usrahh) return;
        currentDM = username;
        dmUsers.add(username);
        
        sdihkid.emit("get_dm_history", {with: username});
        
        document.getElementById('chat-header').textContent = `DM with ${username}`;
        document.getElementById('back-to-group').style.display = 'block';
        chat.innerHTML = '';
        
        if (dmHistory[username]) {
            renderDMHistory(dmHistory[username]);
        }
        
        document.getElementById('dm-indicator').textContent = `DM to ${username}`;
        document.getElementById('dm-indicator').style.display = 'block';
    }

    window.closeDM = function() {
        currentDM = null;
        document.getElementById('chat-header').textContent = 'Group Chat';
        document.getElementById('back-to-group').style.display = 'none';
        document.getElementById('dm-indicator').style.display = 'none';
        chat.innerHTML = '';
        mainchat.forEach(msg => renderMessage(msg));
        window.scrollTo(0, document.body.scrollHeight);
    };

    // Store group messages
    const originalMainChatHandler = sdihkid.onevent.bind(sdihkid);
    sdihkid.onevent = function(packet) {
        if (packet[0] === "mainchat") {
            mainchat.push(packet[1]);
            if (mainchat.length > 10) mainchat.shift();
        }
        return originalMainChatHandler(packet);
    };

    document.querySelector('[dih="yo"]').addEventListener('keydown', function(dih) {
        if (dih.key == "Enter") {
            sendingmyahh();
        }
    });

    function focusin() { 
        document.querySelector('[dih="yo"]').focus();
    }
    document.querySelector('[oc="p"]').addEventListener('click', focusin);
    window.addEventListener('keydown', (dih) => {
        if (dih.target.closest(`popup-window`)) return;
        focusin();
    });
    
    // Initialize color picker grid
    initColorPicker();
});

// User list toggle
window.toggleUserList = function() {
    const userList = document.getElementById('user-list');
    const toggleBtn = document.getElementById('toggle-users');
    if (userList.style.display === 'none') {
        userList.style.display = 'block';
        toggleBtn.style.display = 'none';
        updateUserList();
    } else {
        userList.style.display = 'none';
        toggleBtn.style.display = 'block';
    }
};

function updateUserList() {
    const userListItems = document.getElementById('user-list-items');
    if (!userListItems) return;
    
    userListItems.innerHTML = '';
    
    // Get all connected users from the users object
    Object.keys(window.users).forEach(username => {
        if (username === window.usrahh) return;
        
        const userColor = window.userColors[username] || '#888';
        
        const item = document.createElement('div');
        item.style.cssText = 'padding: 12px; border-bottom: 1px solid var(--border); cursor: pointer; display: flex; align-items: center; gap: 8px;';
        item.setAttribute('data-user', username);
        item.innerHTML = `
            <span style="width: 12px; height: 12px; border-radius: 50%; background: ${userColor}; flex-shrink: 0;"></span>
            <span style="font-weight: 500;">${escapeHtml(username)}</span>
            <span class="dm-badge" style="display: none; background: var(--accent); color: white; border-radius: 50%; width: 18px; height: 18px; font-size: 10px; display: flex; align-items: center; justify-content: center;">•</span>
        `;
        item.onclick = () => openDM(username);
        item.oncontextmenu = (e) => {
            e.preventDefault();
            showUserContextMenu(e, username);
        };
        userListItems.appendChild(item);
    });
}

function showUserContextMenu(e, username) {
    // Remove existing context menu
    const existing = document.querySelector('.user-context-menu');
    if (existing) existing.remove();
    
    const menu = document.createElement('div');
    menu.className = 'user-context-menu';
    menu.style.cssText = `
        position: fixed; top: ${e.clientY}px; left: ${e.clientX}px;
        background: var(--bg-card); border: 1px solid var(--border);
        border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000; min-width: 160px;
    `;
    menu.innerHTML = `
        <div onclick="openDM('${escapeHtml(username)}')" style="padding: 10px 16px; cursor: pointer; border-bottom: 1px solid var(--border);">💬 Open DM</div>
        <div onclick="createDMLink('${escapeHtml(username)}')" style="padding: 10px 16px; cursor: pointer; border-bottom: 1px solid var(--border);">🔗 Create DM Link</div>
        <div onclick="setDMPassword('${escapeHtml(username)}')" style="padding: 10px 16px; cursor: pointer; border-bottom: 1px solid var(--border);">🔒 Set DM Password</div>
        <div onclick="copyDMLink('${escapeHtml(username)}')" style="padding: 10px 16px; cursor: pointer;">🔗 Copy DM Link</div>
    `;
    document.body.appendChild(menu);
    
    document.addEventListener('click', function removeMenu() {
        menu.remove();
        document.removeEventListener('click', removeMenu);
    });
}

function setDMPassword(username) {
    const password = prompt(`Set password for DM with ${username}:`);
    if (!password) return;
    
    sdihkid.emit('set_dm_password', {with: username, password: password});
}

sdihkid.on("dm_password_set", data => {
    alert(`DM password set for ${data.with}`);
});

sdihkid.on("dm_password_error", data => {
    alert(data.message);
});

window.copyDMLink = function(username) {
    const link = `${window.location.origin}${window.location.pathname}?dm=${encodeURIComponent(username)}`;
    navigator.clipboard.writeText(link).then(() => {
        alert('DM link copied to clipboard!');
    });
};

// Color picker initialization
const COLOR_GRID = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    "#F8B500", "#00CED1", "#FF69B4", "#32CD32", "#FF8C00",
    "#9370DB", "#20B2AA", "#FF4500", "#7FFF00", "#DA70D6"
];

function initColorPicker() {
    const grid = document.getElementById('color-picker-grid');
    if (!grid) return;
    
    // Load saved color
    const savedColor = localStorage.getItem('userColor');
    if (savedColor) {
        document.getElementById('custom-color').value = savedColor;
    }
    
    COLOR_GRID.forEach(color => {
        const btn = document.createElement('button');
        btn.style.cssText = `
            width: 40px; height: 40px; border-radius: 50%; border: 3px solid transparent;
            background: ${color}; cursor: pointer; transition: transform 0.2s, border-color 0.2s;
        `;
        btn.dataset.color = color;
        if (color === savedColor) {
            btn.style.borderColor = 'var(--accent)';
        }
        btn.onclick = () => selectColor(color, btn);
        btn.onmouseenter = () => btn.style.transform = 'scale(1.1)';
        btn.onmouseleave = () => btn.style.transform = 'scale(1)';
        grid.appendChild(btn);
    });
}

function selectColor(color, btn) {
    // Update UI
    document.querySelectorAll('#color-picker-grid button').forEach(b => b.style.borderColor = 'transparent');
    btn.style.borderColor = 'var(--accent)';
    
    // Save to localStorage
    localStorage.setItem('userColor', color);
    
    // Send to server
    sdihkid.emit('change_color', {color: color});
}

function setCustomColor() {
    const color = document.getElementById('custom-color').value;
    if (!color) return;
    
    // Update grid selection
    document.querySelectorAll('#color-picker-grid button').forEach(b => b.style.borderColor = 'transparent');
    
    // Save to localStorage
    localStorage.setItem('userColor', color);
    
    // Send to server
    sdihkid.emit('change_color', {color: color});
}

function viewLogs() {
    sdihkid.emit('get_logs', {});
}

function searchGifs() {
    const query = document.getElementById('gif-search').value.trim();
    if (!query) return;
    sdihkid.emit('search_gifs', {query: query});
}

sdihkid.on("gif_results", data => {
    const container = document.getElementById('gif-results');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (data.error) {
        container.innerHTML = `<div style="color: var(--text-danger); padding: 16px; text-align: center;">Error: ${data.error}</div>`;
        return;
    }
    
    if (!data.gifs || data.gifs.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); padding: 16px; text-align: center;">No GIFs found</div>';
        return;
    }
    
    data.gifs.forEach(gif => {
        const img = document.createElement('img');
        img.src = gif.preview;
        img.alt = gif.title;
        img.style.cssText = 'width: 100%; height: 100px; object-fit: cover; border-radius: 4px; cursor: pointer;';
        img.onclick = () => sendGif(gif.url);
        container.appendChild(img);
    });
});

function sendGif(url) {
    if (currentDM) {
        sdihkid.emit("dm", {
            to: currentDM,
            msg: url,
            type: "image"
        });
    } else {
        sdihkid.emit("mainchat", {
            type: "image",
            name: "GIF",
            data: url,
            mimeType: "image/gif"
        });
    }
    // Close settings popup
    document.querySelector('[visible="settings"]').style.display = 'none';
}

function createDMLink(username) {
    sdihkid.emit('create_dm_link', {with: username});
}

sdihkid.on("dm_link_created", data => {
    navigator.clipboard.writeText(data.link).then(() => {
        alert(`DM link copied to clipboard!\n${data.link}`);
    });
});

sdihkid.on("dm_link_joined", data => {
    openDM(data.with);
});

sdihkid.on("dm_link_error", data => {
    alert(data.message);
});
    // Create modal to display logs
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.9); display: flex; flex-direction: column;
        z-index: 10000; padding: 20px;
    `;
    modal.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h2>Server Logs</h2>
            <button onclick="this.closest('div[style*=\"position: fixed\"]').remove()" style="background: var(--accent); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Close</button>
        </div>
        <pre style="flex: 1; overflow: auto; background: #1a1a1a; color: #e0e0e0; padding: 16px; border-radius: 8px; font-family: monospace; font-size: 0.85em; white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(data.logs)}</pre>
    `;
    document.body.appendChild(modal);
});

// Nickname change functionality
function changeNickname() {
    const newNick = document.getElementById('nickname-input').value.trim();
    if (!newNick) {
        alert('Please enter a nickname');
        return;
    }
    sdihkid.emit('change_nickname', {nickname: newNick});
}

sdihkid.on("nickname_success", data => {
    alert(`Nickname changed to ${data.nickname}`);
    document.getElementById('nickname-input').value = '';
    localStorage.setItem('userID', data.nickname);
    window.usrahh = data.nickname;
    // Update local users tracking
    delete window.users[data.old];
    window.users[data.new] = { color: window.userColors[data.old] || '#888' };
    window.userColors[data.new] = window.userColors[data.old] || '#888';
    delete window.userColors[data.old];
    updateUserList();
});

sdihkid.on("nickname_error", data => {
    const cooldownEl = document.getElementById('nickname-cooldown');
    if (data.message.includes('Cooldown')) {
        cooldownEl.textContent = data.message;
        cooldownEl.style.display = 'block';
    } else {
        alert(data.message);
    }
});

sdihkid.on("nickname_changed", data => {
    updateUserList();
    const messages = chat.querySelectorAll('[tag="user"]');
    messages.forEach(msg => {
        if (msg.textContent === data.old) {
            msg.textContent = data.new;
        }
    });
});

function viewNicknameHistory() {
    sdihkid.emit('get_nickname_history', {});
}

sdihkid.on("nickname_history", data => {
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.9); display: flex; flex-direction: column;
        z-index: 10000; padding: 20px;
    `;
    
    let historyHtml = '<h2 style="margin-bottom: 16px;">Nickname Change History</h2>';
    
    if (data.history && Object.keys(data.history).length > 0) {
        for (const [user, changes] of Object.entries(data.history)) {
            historyHtml += `<h3 style="margin-top: 16px; color: var(--accent);">${escapeHtml(user)}</h3>`;
            historyHtml += '<ul style="list-style: none; padding: 0;">';
            changes.forEach(change => {
                const date = new Date(change.timestamp * 1000).toLocaleString();
                historyHtml += `<li style="padding: 8px; background: var(--bg-card); margin-bottom: 8px; border-radius: 4px;">
                    <strong>${escapeHtml(change.old)}</strong> → <strong>${escapeHtml(change.new)}</strong>
                    <br><small style="color: var(--text-muted);">${date} (IP: ${change.ip})</small>
                </li>`;
            });
            historyHtml += '</ul>';
        }
    } else {
        historyHtml += '<p style="color: var(--text-muted);">No nickname changes recorded.</p>';
    }
    
    modal.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h2>Nickname History</h2>
            <button onclick="this.closest('div[style*=\"position: fixed\"]').remove()" style="background: var(--accent); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Close</button>
        </div>
        <div style="flex: 1; overflow: auto;">${historyHtml}</div>
    `;
    document.body.appendChild(modal);
}

// LocalSend functionality
function scanLocalSend() {
    const container = document.getElementById('localsend-devices');
    if (!container) return;
    
    container.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-muted);">Scanning for LocalSend devices...</div>';
    
    // Simulate device discovery (in real implementation, this would use multicast)
    setTimeout(() => {
        container.innerHTML = `
            <div style="padding: 12px; background: var(--bg-card); border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>HostTalk Server</strong>
                    <br><small style="color: var(--text-muted);">This device</small>
                </div>
                <span style="color: var(--accent); font-size: 0.8em;">Current Device</span>
            </div>
            <div style="padding: 12px; background: var(--bg-card); border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>Phone - Pixel 7</strong>
                    <br><small style="color: var(--text-muted);">192.168.1.45:53317</small>
                </div>
                <button onclick="connectLocalSend('192.168.1.45')" style="padding: 6px 12px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Connect</button>
            </div>
            <div style="padding: 12px; background: var(--bg-card); border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>Laptop - MacBook Pro</strong>
                    <br><small style="color: var(--text-muted);">192.168.1.67:53317</small>
                </div>
                <button onclick="connectLocalSend('192.168.1.67')" style="padding: 6px 12px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Connect</button>
            </div>
        `;
    }, 2000);
}

function connectLocalSend(ip) {
    alert(`Connecting to LocalSend device at ${ip}... In a full implementation, this would establish a connection for file transfer.`);
}

function sendViaLocalSend() {
    const fileInput = document.getElementById('file-upload');
    fileInput.click();
    
    // Override the file upload to use LocalSend
    fileInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        alert(`Sending ${file.name} via LocalSend... In a full implementation, this would use the LocalSend REST API to transfer the file directly to the selected device.`);
        fileInput.value = '';
    };
}

// Simulate periodic device discovery
setInterval(() => {
    if (document.getElementById('localsend-devices') && 
        document.getElementById('localsend-devices').style.display !== 'none') {
        scanLocalSend();
    }
}, 30000);

function openImageModal(url) {
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.9); display: flex; align-items: center;
        justify-content: center; z-index: 10000; cursor: zoom-out;
    `;
    modal.innerHTML = `<img src="${url}" style="max-width: 90%; max-height: 90%;">`;
    modal.onclick = () => modal.remove();
    document.body.appendChild(modal);
}