# Deployment Runbook (VPS)

Single command deploy: `docker compose up -d`

## Stack

```
┌─────────────────────────────────────────┐
│  VPS / Localhost                        │
│                                         │
│  ┌───────────────┐    ┌──────────────┐ │
│  │  9router      │    │  ig-qt       │ │
│  │  :20128       │◄───┤  scheduler   │ │
│  │  (LLM + Image │    │  + Telegram  │ │
│  │   gen routing)│    │   review bot │ │
│  └───────────────┘    └──────────────┘ │
│         │                    │          │
│         │                    │ :8080    │
│         ▼                    ▼ /health  │
│   localhost only       localhost only   │
└─────────────────────────────────────────┘
```

## Target

- Linux VPS with Docker + docker compose plugin
- Min: 2 vCPU, 2 GB RAM, 20 GB disk
- Recommended: 2 vCPU, 4 GB RAM (Hetzner CX22 or Contabo VPS S)

## One-time setup

### 1. Provision VPS + install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
# Logout + login for group to apply
```

### 2. Clone + configure

```bash
git clone https://github.com/Nabenns/ig-qtrades4241.git /opt/ig-qt
cd /opt/ig-qt
cp .env.example .env
nano .env
```

Required env vars in `.env`:

```env
# LLM via 9router (default sidecar URL set in docker-compose.yml)
LLM_API_KEY=<your-9router-api-key>

# IG account
IG_USERNAME=...
IG_PASSWORD=...

# News data
NEWSAPI_KEY=...     # https://newsapi.org/register
GNEWS_KEY=...       # https://gnews.io/register
TWELVEDATA_KEY=...  # https://twelvedata.com/register

# Telegram (review bot + alerts)
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat-id>

# Image gen via 9router (Cloudflare connected in router dashboard)
# CF_ACCOUNT_ID and CF_API_TOKEN only needed if you use direct mode

# Optional
APP_ENV=production
BACKUP_DEST=user@backup-host:/backups/ig-qt
```

### 3. Build images + start router

```bash
docker compose build
docker compose up -d router
docker compose logs -f router
# Wait until router shows "Ready"
```

### 4. Configure 9router (one-time)

SSH tunnel to access router dashboard from your laptop:

```bash
ssh -L 20128:localhost:20128 user@your-vps
```

Open http://localhost:20128 in your browser:

1. **Connect Kiro AI** (free Claude unlimited)
   - Providers → Kiro → OAuth (Google/GitHub)
2. **Connect Cloudflare** (free image gen)
   - Media Providers → Image → Cloudflare
   - API Key format: `<account_id>:<api_token>`
3. **Generate API Key** for ig-qt
   - API Keys → Create
   - Copy → paste to `.env` as `LLM_API_KEY`

### 5. First-time IG login (interactive)

⚠️ **For new IG accounts**: skip this step and use hybrid review flow (review in Telegram, post manually via IG app). Login via instagrapi often triggers IG anti-bot challenge that requires manual resolution.

If you have an established account (>3 months active):

```bash
docker compose run --rm ig-qt python scripts/ig_login_first_time.py
```

Follow prompts. On success, `data/ig_session.json` is saved.

### 6. Seed evergreen content (optional)

```bash
docker compose run --rm ig-qt python scripts/generate_evergreen.py
```

### 7. Start the full stack

```bash
docker compose up -d
docker compose logs -f
```

Look for `scheduler_started`. The bot now runs:
- News collection every 15 min
- Analyst every 30 min
- Composer every 10 min (process pending drafts)
- Review send every 2 min (Telegram notification)
- Review poll every 20 sec (process button clicks)
- Publisher every 5 min (skipped if warmup mode active)

### 8. Verify health

```bash
curl -s http://localhost:8080/health | jq
```

Expected: `{"status": "ok", ...}`

## Daily backup cron

Edit crontab:

```bash
crontab -e
```

Add:

```cron
0 4 * * * cd /opt/ig-qt && ./scripts/backup_session.sh >> data/logs/backup.log 2>&1
```

## Operational commands

| Task | Command |
|---|---|
| View logs (both services) | `docker compose logs -f --tail 200` |
| ig-qt logs only | `docker compose logs -f --tail 200 ig-qt` |
| Router logs only | `docker compose logs -f --tail 200 router` |
| Pause publisher | `touch /opt/ig-qt/data/PAUSE` |
| Resume publisher | `rm /opt/ig-qt/data/PAUSE` |
| Restart all | `docker compose restart` |
| Update | `git pull && docker compose build && docker compose up -d` |
| Inspect DB | `docker compose exec ig-qt sqlite3 /app/data/ig_qt.db` |
| Check health | `curl -s http://localhost:8080/health \| jq` |
| Manual collect | `docker compose exec ig-qt python -m ig_qt collect` |
| Manual analyze | `docker compose exec ig-qt python -m ig_qt analyze` |
| Manual compose | `docker compose exec ig-qt python -m ig_qt compose` |
| Warmup status | `docker compose exec ig-qt python -m ig_qt admin warmup-status` |
| Disable warmup | `docker compose exec ig-qt python -m ig_qt admin warmup-disable` |

## Hybrid manual posting (recommended for new accounts)

If skipping IG auto-publish:

1. Pipeline runs as normal (collect → analyze → compose → status='review')
2. Telegram review bot sends preview with 4 buttons
3. Click **📋 Copy Caption** → bot sends caption as separate message (easy copy)
4. Tap-hold image in Telegram → save to phone gallery
5. Open IG app → upload image + paste caption from clipboard

Status `approved` is set but publisher will skip if warmup mode active or if post already manually published. No risk of IG ban from automation.

## Recovery scenarios

### Telegram bot not sending

```bash
docker compose logs ig-qt | grep telegram
# Check TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
# Re-test: docker compose exec ig-qt python scripts/test_review.py send
```

### IG session expired
```bash
docker compose down
docker compose run --rm ig-qt python scripts/ig_login_first_time.py
docker compose up -d
```

### Account challenge (Telegram alert received)
1. Open Instagram app on phone, complete challenge manually
2. Wait 24h
3. On VPS: clear pause state
   ```bash
   docker compose exec ig-qt sqlite3 /app/data/ig_qt.db \
     "UPDATE ig_account_state SET pause_until = NULL, challenge_pending = 0 WHERE id = 1"
   docker compose restart
   ```

### 9router OAuth expired
1. SSH tunnel + open dashboard
2. Re-OAuth provider
3. ig-qt auto-resumes on next interval

### LLM_API_KEY rotation
1. Generate new key in router dashboard
2. Update `.env`
3. `docker compose restart ig-qt`

### VPS migration
1. Provision new VPS, install Docker
2. Clone repo, copy `.env` from secure storage
3. Restore `data/` + `router-data/` from backup
4. `docker compose up -d`

## Security

- `.env` is gitignored. Store backup in password manager.
- `data/ig_session.json` = IG credential. Encrypt for offsite backup.
- Port 8080 (health) and 20128 (router) bind to `127.0.0.1` only — use SSH tunnel for remote access.
- Pin Docker image tag in production (`image: ig-qt:vX.Y.Z`).
- Rotate Telegram bot token, 9router API key, Cloudflare token periodically.

## Monitoring

- **UptimeRobot**: SSH tunnel + check `http://localhost:8080/health`
- **Telegram alerts**: automatic on Challenge, Feedback, failed publish
- **Logs**: `data/logs/app.log` (rotated 100MB / 30 days), `data/logs/errors.log` (90 days)
