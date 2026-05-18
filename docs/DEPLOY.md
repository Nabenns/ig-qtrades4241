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
   - `LLM_BASE_URL` (default `http://router:20128/v1` for sidecar setup)
   - `LLM_API_KEY` — set after first 9router boot (step 6)
   - `IG_USERNAME`, `IG_PASSWORD`
   - `NEWSAPI_KEY`, `GNEWS_KEY`, `TWELVEDATA_KEY`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - `BACKUP_DEST`

5. **Build the ig-qt image:**
   ```bash
   docker compose build
   ```

6. **Start 9router sidecar first + connect a free provider:**

   ```bash
   docker compose up -d router
   docker compose logs -f router
   # Wait until router is ready (HTTP server listening on :20128)
   ```

   Then on your laptop, open SSH tunnel to access the 9router dashboard:

   ```bash
   ssh -L 20128:localhost:20128 user@your-vps
   ```

   Open http://localhost:20128/dashboard in your browser:
   - Initial password: `123456` (change in dashboard settings immediately)
   - **Connect a free provider** — recommended: Kiro AI (Claude Sonnet 4.5 unlimited)
     - Click Providers → Connect → Kiro AI
     - Choose AWS Builder ID / Google / GitHub OAuth
     - Done — model `kr/claude-opus-4.7` (or `kr/claude-sonnet-4.5`) is now available
   - **Generate API key** for ig-qt to use:
     - Dashboard → API Keys → Create new
     - Copy the key, paste into `.env` as `LLM_API_KEY`

7. **First-time IG login (interactive):**
   ```bash
   docker compose run --rm ig-qt python scripts/ig_login_first_time.py
   ```
   Follow prompts. If Instagram requests a verification code (email/SMS), enter it. On success, `data/ig_session.json` is created and backed up to `data/backups/`.

8. **Seed evergreen content pool:**
   ```bash
   docker compose run --rm ig-qt python scripts/generate_evergreen.py
   ```
   Generates ~10 evergreen drafts for dry-day fallback.

9. **Start the full stack:**
   ```bash
   docker compose up -d
   docker compose logs -f
   ```
   Wait until you see `scheduler_started`. Stop following logs with Ctrl+C (the service keeps running).

10. **Verify health:**
    ```bash
    curl -s http://localhost:8080/health | jq
    curl -s http://localhost:20128 -o /dev/null -w "%{http_code}\n"   # 9router responds
    ```
    Expected: `/health` returns JSON with `status: "ok"`. 9router returns HTTP 200.

## Choosing a model

The default is `kr/claude-opus-4.7` for both ranker and composer (set in `config.yaml`). To use a different model or combo:

- **Free options** (via Kiro AI):
  - `kr/claude-opus-4.7` — highest quality, free
  - `kr/claude-sonnet-4.5` — fast, free
  - `kr/glm-5` — free, GLM family
  - `kr/MiniMax-M2.5` — free, long context

- **Custom combo** (configure in 9router dashboard first):
  - Create a combo like `free-forever` with multiple fallbacks
  - Set `models.ranker: free-forever` in `config.yaml`

Edit `config.yaml`, then restart: `docker compose restart ig-qt`.

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
| View logs (both services) | `docker compose logs -f --tail 200` |
| View ig-qt logs only | `docker compose logs -f --tail 200 ig-qt` |
| View router logs only | `docker compose logs -f --tail 200 router` |
| Pause publisher | `touch /opt/ig-qt/data/PAUSE` |
| Resume publisher | `rm /opt/ig-qt/data/PAUSE` |
| Restart all | `docker compose restart` |
| Restart ig-qt only | `docker compose restart ig-qt` |
| Restart router only | `docker compose restart router` |
| Update ig-qt | `git pull && docker compose build && docker compose up -d` |
| Update router | `docker compose pull router && docker compose up -d router` |
| Inspect DB | `docker compose exec ig-qt sqlite3 /app/data/ig_qt.db` |
| Check ig-qt health | `curl -s http://localhost:8080/health \| jq` |
| Check router | `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:20128` |
| Open router dashboard | `ssh -L 20128:localhost:20128 user@vps` then http://localhost:20128 |
| Manual collect | `docker compose exec ig-qt python -m ig_qt collect` |
| Manual analyze | `docker compose exec ig-qt python -m ig_qt analyze` |
| Manual compose | `docker compose exec ig-qt python -m ig_qt compose` |
| Warmup status | `docker compose exec ig-qt python -m ig_qt admin warmup-status` |

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

### 9router OAuth token expired or provider down
1. SSH tunnel to dashboard:
   ```bash
   ssh -L 20128:localhost:20128 user@vps
   ```
2. Open http://localhost:20128/dashboard
3. Re-authenticate the failing provider (Kiro / OpenCode / Vertex)
4. ig-qt auto-resumes on next interval — no restart needed

### LLM_API_KEY needs rotation
1. Generate new API key in 9router dashboard (Dashboard → API Keys → Create)
2. Update `.env` on VPS: `LLM_API_KEY=new-key`
3. `docker compose restart ig-qt`

### VPS lost / migration
1. Provision new VPS, install Docker.
2. Clone repo, copy `.env` from secure storage.
3. `docker compose build`.
4. Restore from backup:
   ```bash
   ./scripts/restore_session.sh
   ```
5. **Also restore router OAuth tokens:** copy `router-data/` from backup or re-OAuth through dashboard.
6. Start: `docker compose up -d`.

## Security

- `.env` is gitignored. Keep a copy in a password manager or sealed vault.
- `data/ig_session.json` grants posting rights to your IG account. Treat as a credential — back up to encrypted offsite.
- Do not expose port 8080 to the public internet without auth. The compose binds to `127.0.0.1` by default.
- Pin the Docker image tag in production (`image: ig-qt:vX.Y.Z`) and bump deliberately.
