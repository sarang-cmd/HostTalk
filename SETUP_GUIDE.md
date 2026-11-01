# HostTalk setup guide

A step by step path from a fresh checkout to a room people use. The README covers the design. This file covers the keystrokes.

## Before you start

- Python 3.10 or newer on the host machine. Check with `python3 --version`.
- The host and the guests on the same network. A guest Wi-Fi with client isolation blocks the room.
- Port 7284 free, or a different port you pick now.
- No internet needed after the first install.

## 1. Get the code

```bash
git clone https://github.com/sarang-cmd/HostTalk
cd HostTalk
```

On Windows, use Git for Windows or download the zip and unpack it.

## 2. Create a virtualenv

Linux and macOS:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

The project uses the virtualenv on purpose. A system Python on recent distributions refuses package installs.

## 3. Set the room password

Browser path, which also sets the room name and the port:

```bash
.venv/bin/python server.py
```

Open `http://127.0.0.1:7284/console`. The first run shows a setup card. Fill in four fields and press Finish setup.

Terminal path, when the machine has no desktop:

```bash
.venv/bin/python -m hosttalk setup \
  --password "the room password" \
  --room "Front room" \
  --port 7284 \
  --non-interactive
```

Both paths write `config.json` into the data folder with mode 0600. The password is stored as a bcrypt hash.

## 4. Start the server

```bash
.venv/bin/python server.py
```

The banner prints three addresses:

- `http://127.0.0.1:7284` for this machine
- `http://192.168.x.x:7284` for the network
- `http://192.168.x.x:7284/console` for the host console

Keep the terminal open, or use one of the service options below.

## 5. Invite the first person

1. Press Invite in the room.
2. Copy the address or let the guest scan the QR code.
3. Give the guest the room password in person or in another channel.
4. The guest opens the address, types a name and the password, and joins.

The console shows the new person under People within a second.

## 6. Check the install

```bash
.venv/bin/python -m hosttalk doctor
```

Each line answers one question:

```
[OK  ] Room password: Set
[OK  ] Data folder: /home/you/.local/share/hosttalk
[OK  ] Free space: 42.0 GB free
[OK  ] Server port: Listening on 7284
[OK  ] Network address: 192.168.1.24 (1 interface)
[WARN] GIF search: Add a GIPHY key to enable search
[OK  ] LocalSend: 0 device(s) seen
```

Warnings are fine. Failures need action before you invite people.

## 7. Keep it running

### Linux, systemd

```bash
sudo cp -r . /opt/hosttalk
sudo bash /opt/hosttalk/deploy/install-service.sh
systemctl status hosttalk
journalctl -u hosttalk -f
```

The helper creates a `hosttalk` system user, a data folder at `/var/lib/hosttalk`, and the unit from `deploy/hosttalk.service`.

### macOS, launchd

```bash
sudo mkdir -p /usr/local/hosttalk
sudo cp -r . /usr/local/hosttalk
sudo cp deploy/com.hosttalk.room.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.hosttalk.room.plist
```

The plist points at `/usr/local/hosttalk` and keeps data in `/Users/Shared/HostTalk`.

### Windows, startup folder

```bat
deploy\hosttalk.bat --headless
```

Put a shortcut to the batch file in `shell:startup`. The batch file creates the virtualenv on first run.

### Docker

```bash
cd deploy
SERVER_PASSWORD="change-this" docker compose up --build -d
docker compose logs -f
```

The compose file uses host networking because LocalSend needs multicast. Without that, discovery lists nothing.

### Behind a proxy

Copy `deploy/Caddyfile` or `deploy/nginx.conf` and point the proxy at `127.0.0.1:7284`. Two settings matter:

- `proxy_buffering off`, so the event stream arrives as it happens
- a read timeout of an hour or more, so the stream stays open when the room is quiet

HTTPS through a local certificate also gives the browser a secure context, which installs the service worker and the phone shortcut.

## 8. Open the firewall

| Platform | Command |
| --- | --- |
| Windows | Allow Python on private networks when the prompt appears |
| Ubuntu | `sudo ufw allow 7284/tcp` |
| Fedora | `sudo firewall-cmd --add-port=7284/tcp --permanent` then reload |
| macOS | Allow incoming connections when the prompt appears |

LocalSend also uses UDP 53317. Open the port when phone transfers matter.

## 9. Change settings later

The console covers every setting. Open `http://127.0.0.1:7284/console` on the host, sign in with the room password, then:

- **Server settings** edits the port, the reach, the files limit, the room cap, the theme default, the log level, the GIPHY key, and the LocalSend identity.
- **Room password** changes the password. Guests keep their sessions until they leave.
- **Rooms** clears messages in a room.
- **People** ends a session.
- **Logs** filters by level and downloads the file.
- **Data** exports a room as JSON and stops the server.

A port or reach change needs a restart. The console marks the change until the server comes back.

## 10. Back up and restore

Back up: copy the data folder. That is the whole state.

```bash
# Linux default
tar -czf hosttalk-backup.tar.gz -C ~/.local/share hosttalk
```

Restore: stop the server, replace the folder, start the server.

The database runs in WAL mode. Copy `hosttalk.db-wal` with the main file, or stop the server before copying.

## Common problems

**The address does not answer from a phone.** Check the network name on both devices. Turn off VPNs. Try the numeric address instead of a hostname. Confirm the firewall rule.

**Join fails with a password error.** The password is case sensitive. Reset it with `.venv/bin/python -m hosttalk reset-password` on the host.

**A name is refused.** That name is bound to another device. Pick another name, or remove the row from the People list after the person leaves.

**The console says the host machine only.** `console_local_only` is on. Open `127.0.0.1` on the host, or turn the setting off in the console when you sign in locally.

**LocalSend devices never appear.** Multicast is blocked. Many guest networks and managed switches isolate clients. Use the browser upload instead.

**The port changes did nothing.** The setting saves to the file. The running process keeps its port until a restart. Stop the server and start it again.

**The log file grows.** It rotates at 2 MB with three backups. Lower the log level to WARNING in the console when the room is busy.

## Uninstall

1. Stop the service.
2. Delete the checkout.
3. Delete the data folder.

Nothing else is left behind. There is no registry entry, no system package, and no cloud account.
