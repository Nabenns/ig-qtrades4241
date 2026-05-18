# Deployment Runbook (VPS)

## Target

- Linux VPS with Docker + docker compose plugin (Ubuntu 22.04+ or Debian 12+).
- Minimum: 2 vCPU, 2 GB RAM, 20 GB disk.
- Recommended: 2 vCPU, 4 GB RAM (Hetzner CX22 ~€4/mo or Contabo VPS S ~$6/mo).

## One-time setup

1. **Provision the VPS** and SSH in.

2. **Install Docker + Compose:**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"
   # Logout + login for group to apply
   ```

3. **Clone repo:**
   ```bash
   git clone https://github.com/Nabenns/ig-qtrades4241.git /opt/ig-qt
   cd /opt/ig-qt
   ```

4. **Configure secrets:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Fill in:
   - `LLM_BASE_URL`, `LLM_API_KEY`
   - `IG_USERNAME`, `IG_PASSWORD`
   - `NEWSAPI_KEY`, `GNEWS_KEY`, `TWELVEDATA_KEY`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - `BACKUP_DEST`

5. **Build the image:**
   ```bash
   docker compose build
   ```

6. **First-time IG login (interactive):**
   ```bash
   docker compose run --rm ig-qt python scripts/ig_login_first_time.py
   ```
   Follow prompts. If Instagram requests a verification code (email/SMS), enter it. On success, `data/ig_session.json` is created and backed up to `data/backups/`.

7. **Seed evergreen content pool:**
   ```bash
   docker compose run --rm ig-qt python scripts/generate_evergreen.py
   ```
   Generates ~10 evergreen drafts for dry-day fallback.

8. **Start the service:**
   ```bash
   docker compose up -d
   docker compose logs -f
   ```
   Wait until you see `scheduler_started`. Stop following logs with Ctrl+C (the service keeps running).

9. **Verify health:**
   ```bash
   curl -s http://localhost:8080/health | jq
   ```
   Expected: JSON with `status: "ok"`.

## Daily backup cron

Edit crontab:

```bash
crontab -e
```

Append:

```cron
0 4 * * * cd /opt/ig-qt && ./scripts/backup_session.sh >> data/logs/backup.log 2>&1
```

Backup runs at 04:00 UTC daily.

## Operational commands

| Task | Command |
|---|---|
| View logs | `docker compose logs -f --tail 200` |
| Pause publisher | `touch /opt/ig-qt/data/PAUSE` |
| Resume publisher | `rm /opt/ig-qt/data/PAUSE` |
| Restart | `docker compose restart` |
| Update | `git pull && docker compose build && docker compose up -d` |
| Inspect DB | `docker compose exec ig-qt sqlite3 /app/data/ig_qt.db` |
| Check health | `curl -s http://localhost:8080/health \| jq` |
| Manual collect | `docker compose exec ig-qt python -m ig_qt collect` |
| Manual analyze | `docker compose exec ig-qt python -m ig_qt analyze` |
| Manual compose | `docker compose exec ig-qt python -m ig_qt compose` |

## Monitoring

1. **UptimeRobot (free):**
   - Add HTTP(s) monitor.
   - Easiest path: keep port 8080 bound to `127.0.0.1` (compose default) and use SSH tunnel `ssh -L 8080:localhost:8080` from your laptop when checking manually.
   - For external monitoring, run a tiny reverse proxy (Caddy/Nginx) on port 80 with HTTP basic auth pointing to `localhost:8080`. UptimeRobot free tier supports keyword check for `"status": "ok"`.

2. **Telegram alerts:** automatic from publisher on Challenge / Feedback / failed publish.

## Recovery scenarios

### Session expired
```bash
docker compose down
docker compose run --rm ig-qt python scripts/ig_login_first_time.py
docker compose up -d
```

### Account challenge (Telegram alert received)
1. Open Instagram app on your phone, log in, complete the challenge manually.
2. Wait 24h to be safe.
3. On VPS:
   ```bash
   docker compose exec ig-qt sqlite3 /app/data/ig_qt.db \
     "UPDATE ig_account_state SET pause_until = NULL, challenge_pending = 0 WHERE id = 1"
   docker compose restart
   ```

### VPS lost / migration
1. Provision new VPS, install Docker.
2. Clone repo, copy `.env` from secure storage.
3. `docker compose build`.
4. Restore from backup:
   ```bash
   ./scripts/restore_session.sh
   ```
5. Start: `docker compose up -d`.

## Security

- `.env` is gitignored. Keep a copy in a password manager or sealed vault.
- `data/ig_session.json` grants posting rights to your IG account. Treat as a credential — back up to encrypted offsite.
- Do not expose port 8080 to the public internet without auth. The compose binds to `127.0.0.1` by default.
- Pin the Docker image tag in production (`image: ig-qt:vX.Y.Z`) and bump deliberately.
