# ig-qt — Session State Snapshot

**Last updated:** 2026-05-18
**Status:** Production-ready, deploy-ready via Docker, manual-posting flow recommended for new accounts.

---

## Repo

- **GitHub:** https://github.com/Nabenns/ig-qtrades4241
- **Branch:** `main`
- **Latest commit:** `a91f3b7` (docs: refresh README + ARCHITECTURE + QUICKSTART)
- **Tests:** 85 passing, mypy strict 64 source files, ruff clean
- **CLI:** `check`, `collect`, `analyze`, `compose`, `run`, `admin warmup-{status,enable,disable}`

## Brand: qtradesedu

- Logo: `assets/logo.png` (gradient teal Q + arrow)
- Handle: `@qtradesedu`
- Account: `benss_workshop` (akun baru — warmup mode aktif by default)
- Color palette: dark forest `#06100E` + mint `#5eead4` + coral `#f87171`

## Stack

- Python 3.12 + uv (`C:\Users\USER\AppData\Roaming\Python\Python314\Scripts\uv.exe`)
- Working dir: `C:\Users\USER\gt\ig-qt`
- Sources: NewsAPI + GNews + RSS (ForexLive/Investing/DailyFX/FXStreet) + Twelve Data + Forex Factory
- LLM: 9router (`http://localhost:20128/v1`), default model `kr/claude-sonnet-4.5`
- Image gen: 9router → Cloudflare Workers AI Flux Schnell
- Image critic: 9router → Cloudflare Mistral 3.1 24B (vision)
- DB: SQLite + SQLAlchemy
- Visual: Tailwind CDN + Geist font + Playwright @ device_scale_factor=2
- Docker: 2 services (router + ig-qt) via `docker compose up -d`

## .env (sudah diisi user; values redacted)

```
LLM_BASE_URL=http://localhost:20128/v1
LLM_API_KEY=<redacted>
IG_USERNAME=benss_workshop
IG_PASSWORD=<redacted>
NEWSAPI_KEY=<redacted>
GNEWS_KEY=<redacted>
TWELVEDATA_KEY=<redacted>
TELEGRAM_BOT_TOKEN=<redacted>
TELEGRAM_CHAT_ID=<redacted>
CF_ACCOUNT_ID=<redacted>
CF_API_TOKEN=<redacted>
```

## 9router providers connected

- **Kiro AI** (LLM): `kr/claude-opus-4.7`, `kr/claude-sonnet-4.5`, `kr/claude-haiku-4.5`, `kr/glm-5`, dll
- **Cloudflare** (image gen): connected as `qt_image_gen`. Format API key: `<account_id>:<api_token>`. Model: `cf/@cf/black-forest-labs/flux-1-schnell`
- **Cloudflare** (vision critic): same connection. Model: `cf/@cf/mistralai/mistral-small-3.1-24b-instruct`

## Pipeline

```
News (15min) → Analyst (30min) → Composer (10min)
                                       ↓
                                Image Gen + Critic (adaptive retry)
                                       ↓
                                Tailwind HTML render @ 2x
                                       ↓
                          Telegram review (4 buttons)
                                       ↓
                          Publisher (5min) — skip kalau warmup
```

Full flow lihat `docs/ARCHITECTURE.md`.

## Status fitur

| Fitur | Status |
|---|---|
| Multi-source collector (5 sources, 15min interval) | ✅ |
| 2-stage LLM analyst (ranker + composer) | ✅ |
| Cloudflare Flux hero image generation | ✅ |
| Mistral 3.1 vision critic + adaptive retry | ✅ |
| 4 template variants (news_breaking, big_number_hero, panel_infographic, headline_card) | ✅ |
| Chart silhouette decorative background | ✅ |
| Telegram review bot dengan 4 inline buttons | ✅ |
| Auto-detect status `review` → kirim ke Telegram | ✅ |
| Callback poll → update post status | ✅ |
| Hybrid manual posting (Copy Caption button) | ✅ |
| Anti-bot publisher tactics (warmup, skip-day, rate limit, posting window) | ✅ |
| Docker compose deployment | ✅ |
| Health endpoint `/health` | ✅ |
| Daily backup script | ✅ |
| Documentation (README, ARCHITECTURE, QUICKSTART, DEPLOY) | ✅ |

## Yang BELUM dikerjain (tergantung user)

- IG Graph API resmi migration (untuk akun baru / safer publish) — defer
- Carousel support (multi-image post) — defer
- Engagement tracking (fetch likes/comments setelah 24h post) — defer
- Reels (video) generation — defer
- Multi-account support — defer

## Workflow harian (recommended untuk akun baru)

1. **Run daemon** (1 terminal): `docker compose up -d` (atau `uv run python -m ig_qt run`)
2. **Bot auto-generate konten** tiap 30 menit (analyze) + 10 menit (compose)
3. **Telegram notif** muncul tiap ada post baru — klik **📋 Copy Caption** + tap-hold image
4. **Manual post** ke IG via app (paste caption + upload image)
5. Status di DB tercatat sebagai approved/rejected (untuk tracking)

## Issue yang udah di-debug

- Multimodal vision Kiro Claude → 400 (Kiro tier gak support image input). Solved dengan switch ke Mistral 3.1 di Cloudflare.
- IG Challenge Required → instagrapi gak bisa auto-resolve `STEP_NAME` baru dari IG. Solved dengan hybrid manual posting flow.
- Telegram parse_mode Markdown → `Bad Request: can't parse entities`. Solved dengan switch ke HTML + html.escape user content.
- DB schema migration setelah add column → `OperationalError: no such column`. Solved dengan `scripts/migrate_db.py` script idempotent.

## Important reminders

- ⚠️ **Akun baru, jangan disable warmup** sampai akun "warmed up" (1-2 minggu manual posting via app)
- ⚠️ **Rotate credentials** setelah testing: IG password, Telegram bot token, 9router API key, Cloudflare token
- ⚠️ **Jangan commit `.env`** — `.gitignore` udah set, tapi double check setiap commit
- ⚠️ **Free tier limits**: NewsAPI/GNews 100 req/day each, Cloudflare 10k img/day. Konservatif aja.

## Test commands cheat sheet

```powershell
# Set PATH (Windows, terminal baru perlu re-set)
$env:Path = "C:\Users\USER\AppData\Roaming\Python\Python314\Scripts;$env:Path"

# Smoke check
uv run python -m ig_qt --check

# Run pipeline manual (dev)
uv run python scripts/reset_compose.py
uv run python -c "import sqlite3; c = sqlite3.connect('data/ig_qt.db'); c.execute('DELETE FROM post_drafts'); c.execute('DELETE FROM review_messages'); c.commit()"
uv run python -m ig_qt analyze
uv run python -m ig_qt compose
uv run python scripts/run_review_bot.py

# All-in-one daemon (production)
uv run python -m ig_qt run

# Verify
uv run pytest -q
uv run mypy --strict src/ scripts/
uv run ruff check src/ tests/ scripts/
```
