# AlgoTrader — Ubuntu Server Deployment Guide

## Prerequisites
- Ubuntu 22.04 LTS server
- Domain name pointed to the server's IP (for SSL)
- External PostgreSQL database (you will fill in `DATABASE_URL`)

---

## Step 1 — Initial Server Hardening

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git ufw fail2ban unattended-upgrades

# Firewall — allow SSH, HTTP, HTTPS only
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

---

## Step 2 — Install Docker Engine

```bash
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

# Allow your user to run Docker without sudo (re-login after this)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

## Step 3 — Install Nginx + Certbot (SSL)

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Copy the Nginx config from the repo
sudo cp /opt/algotrader/nginx/algotrader.conf /etc/nginx/sites-available/algotrader

# Edit the config to replace 'yourdomain.com' with your actual domain
sudo nano /etc/nginx/sites-available/algotrader

# Enable the site
sudo ln -s /etc/nginx/sites-available/algotrader /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # remove the default site

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx

# Issue SSL certificate (replace with your actual domain)
sudo certbot --nginx -d yourdomain.com
# Certbot auto-modifies the nginx config with ssl_certificate lines
sudo systemctl reload nginx
```

---

## Step 4 — Clone Repo and Configure Environment

```bash
sudo mkdir -p /opt/algotrader
sudo chown $USER:$USER /opt/algotrader

git clone https://github.com/your-org/algo-trading.git /opt/algotrader
cd /opt/algotrader

# Create the .env file from the template
cp .env.example .env
nano .env   # fill in all values — DATABASE_URL, MT5_*, SECRET_KEY, domain URL
```

**Required values to set in `.env`:**

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` | MetaTrader 5 credentials |
| `SECRET_KEY` | Random 32+ character string |
| `CORS_ORIGINS` | `["https://yourdomain.com"]` |
| `NEXT_PUBLIC_API_URL` | `https://yourdomain.com` |

```bash
# Create data directories (bind-mounted into backend container)
mkdir -p algo-trading-backend/data/{parquet,raw,processed}
```

---

## Step 5 — Build and Start

```bash
cd /opt/algotrader

# Build images — first run takes ~10 min (TA-Lib compiles from source)
docker compose build --no-cache

# Start in detached mode
docker compose up -d

# Watch startup logs
docker compose logs -f backend    # wait for "Application startup complete"
docker compose logs -f frontend

# Verify both containers are healthy
docker compose ps

# Quick sanity checks
curl http://localhost:8000/health
curl -s http://localhost:3000 | head -5
```

---

## Step 6 — Auto-Start on Reboot (systemd)

```bash
sudo tee /etc/systemd/system/algotrader.service > /dev/null <<'EOF'
[Unit]
Description=AlgoTrader Docker Compose
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/algotrader
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable algotrader
sudo systemctl status algotrader
```

---

## Step 7 — Deploying Updates

```bash
cd /opt/algotrader

# Pull latest code
git pull origin main

# Rebuild changed service(s)
docker compose build backend   # or frontend, or both
docker compose up -d           # recreates only changed containers
```

---

## Useful Commands

```bash
# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Restart a service
docker compose restart backend

# Check migration state
docker compose exec backend alembic current
docker compose exec backend alembic history

# Open a shell in the backend container
docker compose exec backend bash

# Check container health
docker compose ps
```

---

## Cloudflare + Domain Access

With your domain managed in Cloudflare:

**1. Add DNS record in Cloudflare dashboard**

- Type: `A`
- Name: `yourdomain.com` (or `@`)
- Content: your server's IP address
- Proxy: **enabled (orange cloud)**

**2. Set SSL/TLS mode to Full (strict)**

Cloudflare Dashboard → SSL/TLS → Overview → select **Full (strict)**

This means: browser ↔ Cloudflare uses Cloudflare's certificate; Cloudflare ↔ your server uses the Certbot certificate. Both hops are encrypted.

**3. Set your actual domain in `.env`**

```bash
CORS_ORIGINS=["https://yourdomain.com"]
NEXT_PUBLIC_API_URL=https://yourdomain.com
```

`NEXT_PUBLIC_API_URL` is baked into the Next.js bundle **at build time**. After updating `.env`, rebuild the frontend:

```bash
docker compose build frontend
docker compose up -d frontend
```

No Nginx config changes needed — `server_name yourdomain.com` already matches.

---

## PM2 vs Docker for Frontend

**Recommendation: keep Docker. Do not use PM2.**

| | Docker (current setup) | PM2 |
|---|---|---|
| Startup | `docker compose up -d` starts everything | Separate `pm2 start` command |
| Auto-restart | `restart: unless-stopped` in compose | `pm2 startup` + save |
| Consistency | Both services managed identically | Backend in Docker, frontend outside |
| Updates | `docker compose build frontend && up -d` | `npm run build && pm2 restart` |

The `docker-compose.yml` already has `restart: unless-stopped` and the systemd service auto-starts compose on reboot — PM2 would be a second process manager doing the same job.

---

## MT5 Live Trading on Ubuntu (Wine + mt5linux)

### How it works

The `mt5linux` package splits into two halves:
- **Server (Windows side):** runs inside Wine with Python-for-Windows + the native `MetaTrader5` pip package; listens on TCP port 18812
- **Client (Linux side):** `mt5linux` in `requirements.txt`; connects to the socket and proxies all `mt5.*` calls transparently

The backend Docker container reaches the host's Wine process via `host-gateway:18812` (already set in `docker-compose.yml`).

---

### A — Install Wine and Xvfb

```bash
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get install -y wine-stable wine32 wine64 winetricks xvfb x11vnc
```

---

### B — Create a Wine prefix

```bash
export WINEPREFIX=$HOME/.wine-mt5
export WINEARCH=win64

# Start a virtual display (headless X server)
Xvfb :99 -screen 0 1024x768x16 &
export DISPLAY=:99

# Initialise the Wine prefix
wineboot --init
winetricks corefonts vcrun2019
```

---

### C — Install Python 3.11 for Windows inside Wine

Download the **Windows x64 installer** for Python 3.11 from python.org, then:

```bash
DISPLAY=:99 WINEPREFIX=$HOME/.wine-mt5 \
  wine python-3.11.9-amd64.exe /quiet InstallAllUsers=1 PrependPath=1

# Verify
WINEPREFIX=$HOME/.wine-mt5 wine python --version
```

---

### D — Install MetaTrader5 and mt5linux inside Wine's Python

```bash
WINEPREFIX=$HOME/.wine-mt5 wine python -m pip install --upgrade pip
WINEPREFIX=$HOME/.wine-mt5 wine python -m pip install MetaTrader5 mt5linux
```

---

### E — Install MetaTrader5 terminal

Download `mt5setup.exe` from your broker (XM, Exness, etc.), then:

```bash
DISPLAY=:99 WINEPREFIX=$HOME/.wine-mt5 wine mt5setup.exe
```

MT5 will open in the virtual display. To see and interact with it (for first login), use x11vnc:

```bash
x11vnc -display :99 -nopw -listen localhost -xkb &
# Then connect via VNC viewer: ssh -L 5900:localhost:5900 user@server
# Open localhost:5900 in your VNC viewer, log in to MT5, enable AutoTrading
```

Once logged in and AutoTrading is enabled, credentials are saved in the Wine prefix.

---

### F — Start the mt5linux socket bridge

```bash
DISPLAY=:99 WINEPREFIX=$HOME/.wine-mt5 \
  wine python -c "from mt5linux import Server; Server().start()"
```

This starts the server listening on `0.0.0.0:18812`. Keep it running in a separate terminal or move to systemd (next step).

---

### G — Systemd service for the bridge

Create `/etc/systemd/system/xvfb.service`:

```bash
sudo tee /etc/systemd/system/xvfb.service > /dev/null <<'EOF'
[Unit]
Description=Xvfb virtual display :99
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1024x768x16
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

Create `/etc/systemd/system/mt5-bridge.service` (replace `ubuntu` with your username):

```bash
sudo tee /etc/systemd/system/mt5-bridge.service > /dev/null <<'EOF'
[Unit]
Description=MT5 Linux Socket Bridge (Wine)
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
User=ubuntu
Environment=DISPLAY=:99
Environment=WINEPREFIX=/home/ubuntu/.wine-mt5
ExecStart=/usr/bin/wine python -c "from mt5linux import Server; Server().start()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

Enable both:

```bash
sudo systemctl daemon-reload
sudo systemctl enable xvfb mt5-bridge
sudo systemctl start xvfb mt5-bridge
sudo systemctl status mt5-bridge
```

---

### H — Configure `.env` for live trading

```bash
MT5_HOST=host-gateway    # Docker container reaches host via this name
MT5_PORT=18812
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=XM-Real       # use XM-Demo for demo account
TRADING_MODE=live
```

After updating `.env`, restart the backend:

```bash
docker compose restart backend
```

---

### I — Verify the bridge

From the **server host** (not inside Docker):

```bash
python3 -c "
from mt5linux import MetaTrader5
mt5 = MetaTrader5('127.0.0.1', 18812)
print('Connected:', mt5.initialize())
print('Account:', mt5.account_info())
mt5.shutdown()
"
```

Expected output: `Connected: True` and your account details.

---

### J — Enable live trading via the API

Live trading is enabled per-symbol via the API (not the CLI). After `docker compose up -d`:

```bash
# List available configs
curl https://yourdomain.com/api/v1/live-trades/configs

# Enable a config by ID
curl -X POST https://yourdomain.com/api/v1/live-trades/configs/1/enable
```

APScheduler then fires the bar handler at **minute=2 of every hour** (H1 bar close). Check logs:

```bash
docker compose logs -f backend
# Look for: [live_bar] symbol=XAUUSD signal=BUY ...
```

> **Note:** For demo/paper trading without MT5, set `TRADING_MODE=paper` and skip the Wine setup entirely.
