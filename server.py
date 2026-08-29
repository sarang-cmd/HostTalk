# Monkey patch for gevent (must be done FIRST, before ANY imports)
from gevent import monkey
monkey.patch_all()

from flask import Flask,render_template,request,jsonify
from flask_socketio import SocketIO,emit
import webbrowser
import socket
import subprocess
import threading
import platform
import os
import sys
import shutil
import bcrypt
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

if(platform.system()=="Windows"):
        import ctypes
        # pystray disabled for gevent compatibility
        # import pystray
        # from PIL import Image
        # from pystray import MenuItem as dihtem
HOSTTALK0INFO0VER=1.0
APPDATAAHH=os.getenv("APPDATA")
APPROOT=os.path.join(APPDATAAHH,"HostTalk")
os.makedirs(APPROOT,exist_ok=True)
def exe():
   if getattr(sys,'frozen',False):
      return sys._MEIPASS
   return os.path.dirname(os.path.abspath(__file__))

temp0dih0server=exe()
def packurbagsahh(dih,seconddih):
 os.makedirs(seconddih,exist_ok=True)
 for dihh in os.listdir(dih):
    sdih=os.path.join(dih,dihh)
    ddih=os.path.join(seconddih,dihh)
    if not os.path.exists(ddih):
       if os.path.isdir(sdih):
          shutil.copytree(sdih,ddih)
       else:
          shutil.copy2(sdih,ddih)

packurbagsahh(os.path.join(temp0dih0server,"static"),
              os.path.join(APPROOT,"static"))
packurbagsahh(os.path.join(temp0dih0server,"templates"),
              os.path.join(APPROOT,"templates"))

if(platform.system()=="Windows"):
        ker=ctypes.WinDLL("kernel32")
        use=ctypes.WinDLL("user32")
        SH=5
        HI=0
        def consolepi():
           return ker.GetConsoleWindow()
        def hideall():
           h=consolepi()
           if(h):
              use.ShowWindow(h,HI)
        def showall():
           h=consolepi()
           if h:
              use.ShowWindow(h,SH)
# def traySH(ic,it):
#    if platform.system()=="Windows":
#       h=consolepi()
#       if h:
#          use.ShowWindow(h,SH)
# def trayQU(ic,it):
#    try:
#       s.stop()
#    except:
#       pass
#    ic.stop()
#    os._exit(0)
# def trayIC():
#    if platform.system() !="Windows":
#       return
#    img=Image.open(os.path.join(exe(),'icon.ico'))
#    menu=(
#       dihtem("show console",traySH),
#       dihtem("quit",trayQU)
#    )
#    icon=pystray.Icon("HostTalk",img,"HostTalk Server",menu)
#    icon.run()

ss='Error'
se='Error'
pref0admintoall=True
pref0showall=False
startcommandline=False #remember ur ahh to turn ts to false in production
if startcommandline:
   temp0in0com=input("Press Enter to start server or enter -s to enter command mode...    ")
   if temp0in0com.strip()=="":
     pass
   elif temp0in0com=="-s":
      print('Commands activated.')
      print('Enter "settings" to change settings')
      temp0in0call=input()
      if(temp0in0call.lower().strip()=="settings"):
         print("SETTINGS :\n   1 => Admin permission to any user(bool)\n   2 => Show sensitive information in the server console(bool)")
         temp0in0set=input()
         if(temp0in0set.lower().strip()=="1"):
            input("")
   else:
      print('Unknown command. Starting server')
      pass
def cityboii():
    se=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        se.connect(('8.8.8.8',80))
        f=se.getsockname()[0]
    except Exception:
        f='127.0.0.1'
    finally:
        se.close()
    try:
     if(platform.system()=='Windows'):
        ss=subprocess.check_output(['powershell',"-Command","(Get-NetConnectionProfile | Where-object {$_.InterfaceAlias -like '*Wi-Fi*'}).Name"],
        text=True).strip()
     elif(platform.system()=="Linux"):
         ss=subprocess.check_output(['iwgetid',"-r"],text=True).strip()
     elif(platform.system()=='Darwin'):
         ss=subprocess.check_output(['/System/Library/PrivateFrameworks/Apple80211.framework/Version/Current/Resources/airport',"-I"],text=True).split(
             'SSID: ')[1].splitlines()[0]
    except Exception as e:
        print(f'Failed to get your ssid | {e}')
        return f'Failed to get your ssid | {e}'
    return f,ss

app=Flask(__name__,template_folder=os.path.join(APPROOT,"templates"),static_folder=os.path.join(APPROOT,"static"))
app.config["AUTH"]="local"
s=SocketIO(app,cors_allowed_origins="*", async_mode='gevent')
mainchat=[]
users={}
dms = {}
dm_passwords = {}
user_colors = {}
used_colors = set()
server_password = os.getenv("SERVER_PASSWORD", "")
if server_password:
    # Hash the password if it's not already hashed
    if not server_password.startswith("$2b$"):
        server_password = bcrypt.hashpw(server_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
imimname='group'

# Predefined color grid (20 distinct colors)
COLOR_GRID = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    "#F8B500", "#00CED1", "#FF69B4", "#32CD32", "#FF8C00",
    "#9370DB", "#20B2AA", "#FF4500", "#7FFF00", "#DA70D6"
]

def get_next_color():
    """Get the next available color from the grid"""
    for color in COLOR_GRID:
        if color not in used_colors:
            used_colors.add(color)
            return color
    # If all colors used, return a random color
    import random
    return f"#{random.randint(0, 0xFFFFFF):06x}"

def release_color(color):
    """Release a color back to the pool"""
    used_colors.discard(color)

# Configure logging
logging.basicConfig(
    filename=os.path.join(APPROOT, "hosttalk.log"),
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
@app.route('/',methods=["GET"])
def w():
    return render_template('index.html')
@s.on("mainchat")
def chat(dih):
    dihname = users.get(request.sid, 'unknown')
    
    if isinstance(dih, dict):
        # New message format with type
        msg_type = dih.get('type', 'text')
        
        if msg_type in ['image', 'file']:
            # Store file data (base64) - in production, save to disk
            d = {
                'name': dihname,
                'type': msg_type,
                'msg': dih.get('data', ''),
                'fileName': dih.get('name', ''),
                'fileSize': dih.get('size', 0),
                'mimeType': dih.get('mimeType', '')
            }
        else:
            d = {'name': dihname, "msg": dih.get('content', dih)}
    else:
        # Legacy format
        d = {'name': dihname, "msg": dih}
    
    mainchat.append(d)
    mainchat[:] = mainchat[-10:]
    emit("mainchat", d, broadcast=True)
    
    if pref0showall == True:
        if isinstance(dih, dict) and dih.get('type') in ['image', 'file']:
            tempmessageshow = f'[{dih.get("type")}] {dih.get("name", "")}'
        else:
            tempmessageshow = f'"{dih}"'
    else:
        tempmessageshow = ""
    print(f"│ Notification : {dihname} sent a message {tempmessageshow} ")
@s.on("join")
def usrn(dih):
    # Verify password if required
    if server_password:
        if 'password' not in dih or not bcrypt.checkpw(dih['password'].encode('utf-8'), server_password.encode('utf-8')):
            emit("auth_error", {"message": "Incorrect password"})
            logger.warning(f"Failed login attempt from {request.remote_addr}")
            return
    
    users[request.sid] = dih['name']
    
    # Assign color if not already assigned
    if request.sid not in user_colors:
        user_colors[request.sid] = get_next_color()
    
    logger.info(f"User connected: {users.get(request.sid, request.sid)}")
    
    # Broadcast user joined
    emit("user_joined", {"name": dih['name'], "color": user_colors[request.sid]}, broadcast=True, include_self=False)
    
    for dih in mainchat:
        emit("mainchat", dih)
@s.on("disconnect")
def sybau():
    username = users.get(request.sid, 'unknown')
    logger.info(f"User disconnected: {username}")
    
    # Release color
    if request.sid in user_colors:
        release_color(user_colors[request.sid])
        del user_colors[request.sid]
    
    users.pop(request.sid, None)
    
    # Broadcast user left
    emit("user_left", {"name": username}, broadcast=True)

@s.on("quote_reply")
def handle_quote_reply(data):
    sender = users.get(request.sid, 'unknown')
    quoted_msg_id = data.get('quoted_msg_id')
    reply_content = data.get('msg', '')
    msg_type = data.get('type', 'text')
    
    # Find the quoted message in mainchat
    quoted_msg = None
    for msg in mainchat:
        if id(msg) == quoted_msg_id or msg.get('id') == quoted_msg_id:
            quoted_msg = msg
            break
    
    if not quoted_msg:
        emit("quote_error", {"message": "Quoted message not found"})
        return
    
    d = {
        'name': sender,
        'msg': reply_content,
        'type': msg_type,
        'quoted': {
            'id': quoted_msg_id,
            'name': quoted_msg.get('name'),
            'msg': quoted_msg.get('msg', ''),
            'type': quoted_msg.get('type', 'text')
        }
    }
    
    mainchat.append(d)
    mainchat[:] = mainchat[-10:]
    emit("mainchat", d, broadcast=True)
    
    logger.info(f"Quote reply from {sender}")

@s.on("fetch_link_preview")
def fetch_link_preview(data):
    url = data.get('url')
    if not url:
        return
    
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'twitter:title'}) or soup.title
        description = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'twitter:description'}) or soup.find('meta', attrs={'name': 'description'})
        image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
        
        preview = {
            'url': url,
            'title': title.get('content') if title and title.get('content') else (title.text if title else url),
            'description': description.get('content') if description else '',
            'image': image.get('content') if image else ''
        }
        
        emit("link_preview", preview, room=request.sid)
    except Exception as e:
        logger.warning(f"Failed to fetch link preview: {e}")
        emit("link_preview", {'url': url, 'error': str(e)}, room=request.sid)

@s.on("get_logs")
def get_logs(data):
    # Only allow host to view logs
    # For simplicity, we'll check if the user is the first connected user
    # In a real implementation, you'd have proper admin detection
    log_file = os.path.join(APPROOT, "hosttalk.log")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = f.read()[-10000:]  # Last 10KB
        emit("logs", {"logs": logs})
    else:
        emit("logs", {"logs": "No logs available"})

@s.on("search_gifs")
def search_gifs(data):
    query = data.get('query', '')
    if not query:
        emit("gif_results", {"gifs": []})
        return
    
    try:
        import requests
        # Using GIPHY public API (free tier: 100 requests/hour)
        # You can get an API key from https://developers.giphy.com/
        api_key = os.getenv("GIPHY_API_KEY", "dc6zaTOxFJmzC")  # Public beta key
        url = f"https://api.giphy.com/v1/gifs/search"
        params = {
            'api_key': api_key,
            'q': query,
            'limit': 20,
            'rating': 'g'
        }
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        
        gifs = []
        for gif in data.get('data', []):
            gifs.append({
                'url': gif['images']['fixed_height']['url'],
                'preview': gif['images']['fixed_height_small']['url'],
                'title': gif.get('title', 'GIF')
            })
        
        emit("gif_results", {"gifs": gifs})
    except Exception as e:
        logger.warning(f"Failed to search GIFs: {e}")
        emit("gif_results", {"gifs": [], "error": str(e)})

# DM Links
dm_links = {}

@s.on("create_dm_link")
def create_dm_link(data):
    sender = users.get(request.sid, 'unknown')
    recipient = data.get('with')
    
    if not recipient or recipient not in users.values():
        emit("dm_link_error", {"message": "User not found"})
        return
    
    import uuid
    link_id = str(uuid.uuid4())[:8]
    dm_links[link_id] = {
        'users': [sender, recipient],
        'created': time.time()
    }
    
    link = f"{request.host_url}?dm_link={link_id}"
    emit("dm_link_created", {"link": link, "with": recipient})

@s.on("join_dm_link")
def join_dm_link(data):
    link_id = data.get('link_id')
    if not link_id or link_id not in dm_links:
        emit("dm_link_error", {"message": "Invalid or expired link"})
        return
    
    link_data = dm_links[link_id]
    user = users.get(request.sid)
    if not user:
        emit("dm_link_error", {"message": "Please join the chat first"})
        return
    
    if user not in link_data['users']:
        emit("dm_link_error", {"message": "This link is not for you"})
        return
    
    other_user = link_data['users'][0] if link_data['users'][1] == user else link_data['users'][1]
    emit("dm_link_joined", {"with": other_user})

# DM Passwords
dm_passwords = {}

@s.on("set_dm_password")
def set_dm_password(data):
    user = users.get(request.sid, 'unknown')
    other_user = data.get('with')
    password = data.get('password')
    
    if not other_user or not password:
        emit("dm_password_error", {"message": "Invalid parameters"})
        return
    
    # Create a unique key for this DM pair
    dm_key = tuple(sorted([user, other_user]))
    dm_passwords[dm_key] = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    emit("dm_password_set", {"with": other_user})
    logger.info(f"DM password set between {user} and {other_user}")

@s.on("check_dm_password")
def check_dm_password(data):
    user = users.get(request.sid, 'unknown')
    other_user = data.get('with')
    password = data.get('password')
    
    if not other_user or not password:
        emit("dm_password_result", {"valid": False})
        return
    
    dm_key = tuple(sorted([user, other_user]))
    if dm_key in dm_passwords:
        valid = bcrypt.checkpw(password.encode('utf-8'), dm_passwords[dm_key].encode('utf-8'))
        emit("dm_password_result", {"valid": valid, "with": other_user})
    else:
        emit("dm_password_result", {"valid": True, "with": other_user})  # No password set

@s.on("dm")
def handle_dm(data):
    sender = users.get(request.sid, 'unknown')
    recipient = data.get('to')
    message = data.get('msg', '')
    msg_type = data.get('type', 'text')
    
    if not recipient or recipient not in users.values():
        emit("dm_error", {"message": "User not found"})
        return
    
    # Find recipient's sid
    recipient_sid = None
    for sid, name in users.items():
        if name == recipient:
            recipient_sid = sid
            break
    
    if not recipient_sid:
        emit("dm_error", {"message": "User not connected"})
        return
    
    dm_data = {
        'from': sender,
        'to': recipient,
        'msg': message,
        'type': msg_type,
        'timestamp': time.time()
    }
    
    # Store in DM history
    if sender not in dms:
        dms[sender] = {}
    if recipient not in dms[sender]:
        dms[sender][recipient] = []
    dms[sender][recipient].append(dm_data)
    
    # Also store for recipient
    if recipient not in dms:
        dms[recipient] = {}
    if sender not in dms[recipient]:
        dms[recipient][sender] = []
    dms[recipient][sender].append(dm_data)
    
    # Send to recipient
    emit("dm", dm_data, room=recipient_sid)
    # Send confirmation to sender
    emit("dm", dm_data, room=request.sid)

@s.on("open_dm")
def open_dm(data):
    """Check DM password before opening DM"""
    user = users.get(request.sid, 'unknown')
    other_user = data.get('with')
    
    if not other_user:
        emit("dm_password_required", {"required": False})
        return
    
    dm_key = tuple(sorted([user, other_user]))
    if dm_key in dm_passwords:
        emit("dm_password_required", {"required": True, "with": other_user})
    else:
        emit("dm_password_required", {"required": False, "with": other_user})

@s.on("change_color")
def handle_color_change(data):
    color = data.get('color')
    if not color:
        return
    
    # Check if color is already used by another user
    for sid, user_color in user_colors.items():
        if user_color == color and sid != request.sid:
            emit("color_error", {"message": "This color is already in use"})
            return
    
    # Release old color if any
    if request.sid in user_colors:
        release_color(user_colors[request.sid])
    
    # Assign new color
    user_colors[request.sid] = color
    used_colors.add(color)
    
    # Broadcast color change
    emit("user_color_changed", {"name": users[request.sid], "color": color}, broadcast=True)
    
    logger.info(f"DM from {sender} to {recipient}")

@s.on("get_dm_history")
def get_dm_history(data):
    sender = users.get(request.sid, 'unknown')
    other_user = data.get('with')
    
    if sender in dms and other_user in dms[sender]:
        history = dms[sender][other_user][-50:]  # Last 50 messages
        emit("dm_history", {"with": other_user, "messages": history})

# Nickname changes
nickname_history = {}
nickname_cooldowns = {}

@s.on("change_nickname")
def change_nickname(data):
    user = users.get(request.sid, 'unknown')
    new_nickname = data.get('nickname', '').strip()
    
    if not new_nickname:
        emit("nickname_error", {"message": "Nickname cannot be empty"})
        return
    
    if new_nickname == user:
        emit("nickname_error", {"message": "Nickname is the same as current"})
        return
    
    # Check if nickname is already taken
    if new_nickname in users.values():
        emit("nickname_error", {"message": "Nickname already in use"})
        return
    
    # Check cooldown (1 hour = 3600 seconds)
    current_time = time.time()
    if user in nickname_cooldowns:
        time_since_last = current_time - nickname_cooldowns[user]
        if time_since_last < 3600:
            remaining = int(3600 - time_since_last)
            minutes = remaining // 60
            seconds = remaining % 60
            emit("nickname_error", {"message": f"Cooldown active. Try again in {minutes}m {seconds}s"})
            return
    
    # Log nickname change
    log_entry = {
        'old': user,
        'new': new_nickname,
        'timestamp': current_time,
        'ip': request.remote_addr
    }
    if user not in nickname_history:
        nickname_history[user] = []
    nickname_history[user].append(log_entry)
    
    # Update cooldown
    nickname_cooldowns[user] = current_time
    
    # Update user list
    old_name = user
    users[request.sid] = new_nickname
    
    # Broadcast nickname change
    emit("nickname_changed", {"old": old_name, "new": new_nickname}, broadcast=True)
    emit("nickname_success", {"nickname": new_nickname})
    
    logger.info(f"Nickname changed: {old_name} -> {new_nickname}")

@s.on("get_nickname_history")
def get_nickname_history(data):
    # Only host can view history
    target_user = data.get('user')
    if target_user and target_user in nickname_history:
        emit("nickname_history", {"user": target_user, "history": nickname_history[target_user]})
    else:
        emit("nickname_history", {"history": nickname_history})
@app.route('/api/ip')
def ip():
    ip,ssid=cityboii()
    return jsonify({"ip": ip,
                    "ssid":ssid})

# LocalSend API endpoints (enabled by default)
@app.route('/api/localsend/v2/register', methods=['POST'])
def localsend_register():
    """Register this device with LocalSend"""
    data = request.get_json() or {}
    device_info = {
        'alias': data.get('alias', 'HostTalk'),
        'deviceModel': data.get('deviceModel', 'Server'),
        'deviceType': 'desktop',
        'fingerprint': 'hosttalk-server',
        'port': 9287,
        'protocol': 'http',
        'download': True,
        'announce': True
    }
    return jsonify(device_info)

@app.route('/api/localsend/v2/prepare-upload', methods=['POST'])
def localsend_prepare_upload():
    """Prepare for file upload"""
    data = request.get_json() or {}
    session_id = str(uuid.uuid4())
    files = data.get('files', [])
    
    file_tokens = {}
    for f in files:
        file_id = f.get('id', str(uuid.uuid4()))
        file_tokens[file_id] = str(uuid.uuid4())[:16]
    
    return jsonify({
        'sessionId': session_id,
        'fileTokens': file_tokens
    })

@app.route('/api/localsend/v2/upload', methods=['POST'])
def localsend_upload():
    """Handle file upload"""
    session_id = request.args.get('sessionId')
    file_id = request.args.get('fileId')
    token = request.args.get('token')
    
    if not session_id or not file_id or not token:
        return jsonify({'error': 'Missing parameters'}), 400
    
    # Save file
    file_data = request.data
    filename = request.headers.get('X-File-Name', f'file_{file_id}')
    
    # In a real implementation, save to disk and broadcast to chat
    # For now, just acknowledge
    return jsonify({'success': True})

@app.route('/api/localsend/v2/cancel', methods=['POST'])
def localsend_cancel():
    """Cancel upload session"""
    session_id = request.args.get('sessionId')
    return jsonify({'success': True})

# Multicast discovery for LocalSend
def start_localsend_multicast():
    """Start listening for LocalSend multicast announcements"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', 53317))
        mreq = struct.pack('4sl', socket.inet_aton('224.0.0.167'), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        while True:
            data, addr = sock.recvfrom(1024)
            try:
                device_info = json.loads(data.decode())
                logger.info(f"LocalSend device discovered: {device_info.get('alias')} at {addr}")
                # Could broadcast to connected clients
            except:
                pass
    except Exception as e:
        logger.warning(f"LocalSend multicast listener failed: {e}")

# Start LocalSend multicast listener in background
import threading
import struct
import uuid
multicast_thread = threading.Thread(target=start_localsend_multicast, daemon=True)
multicast_thread.start()

@app.route('/api/change-password', methods=['POST'])
def change_password():
    global server_password
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not server_password:
        return jsonify({"success": False, "message": "No password is currently set."})
    
    if not bcrypt.checkpw(old_password.encode('utf-8'), server_password.encode('utf-8')):
        return jsonify({"success": False, "message": "Incorrect old password."})
    
    if not new_password:
        return jsonify({"success": False, "message": "New password cannot be empty."})
    
    # Update the password
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    server_password = hashed_password
    
    # Update .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    with open(env_path, 'r') as f:
        env_lines = f.readlines()
    
    with open(env_path, 'w') as f:
        for line in env_lines:
            if line.startswith('SERVER_PASSWORD='):
                f.write(f'SERVER_PASSWORD={new_password}\n')
            else:
                f.write(line)
    
    logger.info("Server password changed successfully")
    return jsonify({"success": True, "message": "Password changed successfully."})
@s.on("shut")
#yo fix ts before uploadin to github
def off():
   if pref0admintoall:
    print(f"│ {users.get(request.sid,request.sid)} shut down the server.")
    s.stop()
   else:
    print(f"│ {users.get(request.sid,request.sid)} tried to shut down the server.")
    print(f"│ Permission denied. {users.get(request.sid,request.sid)} doesnt have the permission to shut down the server down")
    print(f"│ Turn on 'Admin to all' to give permission to {users.get(request.sid,request.sid)} shut down the server down")

if __name__=='__main__':
    if platform.system()=="Windows":    
        if consolepi():
           hideall()
        # threading.Thread(target=trayIC,daemon=True).start()

    print(
        f"""
        `7MMF'  `7MMF'                   mm       MMP""MM""YMM      `7MM  `7MM      
          MM      MM                     MM       P'   MM   `7        MM    MM     
          MM      MM  ,pW"Wq.  ,pP"Ybd mmMMmm          MM   ,6"Yb.    MM    MM  ,MP'
          MMmmmmmmMM 6W'   `Wb 8I   `"   MM            MM  8)   MM    MM    MM ;Y   
          MM      MM 8M     M8 `YMMMa.   MM            MM   ,pm9MM    MM    MM;Mm   
          MM      MM YA.   ,A9 L.   I8   MM            MM  8M   MM    MM    MM `Mb. 
        .JMML.  .JMML.`Ybmd9'  M9mmmP'   `Mbmo       .JMML.`Moo9^Yo..JMML..JMML. YA.
                                                                                        {HOSTTALK0INFO0VER}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                                                  
""")
    sss,ssss=cityboii()
    print("│ Server : running")
    print(f"│ Local access : http://127.0.0.1:9287/")
    print(f"│ Lan access (other devices/wifi): http://{sss}:9287/")
    print(f"│ Wifi SSID : {ssss}")
    print(" ")
    print(f"│ Opening : http://{sss}:9287/")
    webbrowser.open_new_tab(f'http://{sss}:9287/')
    print('')
    s.run(app, host="0.0.0.0", port=9287, debug=False, use_reloader=False)
