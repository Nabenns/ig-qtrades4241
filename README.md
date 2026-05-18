# ig-qt — qtradesedu

Auto-generate Instagram konten edukasi forex/finance dengan AI:
- Fetch berita real-time (NewsAPI, GNews, RSS, Forex Factory)
- LLM rank + generate caption (Claude via 9router free tier)
- Cinematic hero image (Cloudflare Flux) dengan vision-based quality critic
- Tailwind + Geist HTML render @ retina 2x
- Telegram review workflow dengan inline approve/reject
- Hybrid posting: AI generate, manual upload ke IG (anti-ban friendly)

## Quick start

```bash
git clone https://github.com/Nabenns/ig-qtrades4241.git
cd ig-qtrades4241
cp .env.example .env  # edit dengan credentials
docker compose up -d
```

Buka `http://localhost:20128` (router dashboard) untuk setup providers, lalu cek health di `http://localhost:8080/health`.

Detail lengkap: [docs/QUICKSTART.md](docs/QUICKSTART.md)

## Stack

```
┌──────────────────────────────────────────────────┐
│                                                  │
│  9router :20128  ◄────  ig-qt scheduler          │
│   Kiro AI                                        │
│   Cloudflare Flux                                │
│                                                  │
│              Telegram review bot                 │
│              ↕                                   │
│              User (approve/reject)               │
│                                                  │
└──────────────────────────────────────────────────┘
```

- **Python 3.12** + uv + APScheduler + SQLAlchemy + SQLite
- **Playwright** + **Tailwind CSS** + **Geist** font untuk visual rendering
- **mplfinance** untuk chart visualization
- **instagrapi** untuk IG API (optional, hybrid mode skip)
- **9router** sebagai single API gateway untuk LLM + image gen
- **Docker compose** untuk single-command deploy

## Pipeline

```
News (15min) → Analyst (30min) → Composer (10min)
                                       ↓
                                Image Gen + Critic
                                       ↓
                                Tailwind HTML render
                                       ↓
                          Telegram review (approve/reject)
                                       ↓
                          Publisher (5min) or Manual post
```

Detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Features

### AI agentic loop

1. **Opus generate** prompt cinematic untuk hero image
2. **Cloudflare Flux** render image
3. **Mistral Vision** review image (score 0-1)
4. Adaptive retry: kalau score < 0.7, tweak prompt + regenerate (max 2 retry)
5. Pilih best score → save sebagai hero.png

### Telegram review

Setiap post baru, bot kirim foto + caption + 4 button:

```
┌──────────────────────┐
│  POST REVIEW #42     │
│  fed_hike · feed     │
│  conf 0.92           │
│                      │
│  [HERO IMAGE]        │
│                      │
│  📝 Update pasar...  │
│  ⚠️ Fed hike lagi   │
│  ...                 │
│                      │
│ ✅ Approve  ❌ Reject │
│ 📋 Caption  🔄 Regen │
└──────────────────────┘
```

User click button → bot poll callback → status update.

### Anti-ban tactics (publisher)

- Posting window 06-23 WIB
- Skip-day random 14% probability per day (deterministic seed)
- Rate limits konservatif: 2 feed/day, 5 story/day
- Pre-publish warmup (timeline read + 8-15s sleep)
- Pause-on-challenge 7 hari + Telegram alert
- Kill switch via `data/PAUSE` file

## Operasional

```bash
# All-in-one daemon
docker compose up -d

# View logs
docker compose logs -f --tail 200

# Manual commands
docker compose exec ig-qt python -m ig_qt collect    # fetch news
docker compose exec ig-qt python -m ig_qt analyze    # generate drafts
docker compose exec ig-qt python -m ig_qt compose    # render visual

# Admin
docker compose exec ig-qt python -m ig_qt admin warmup-status
docker compose exec ig-qt python -m ig_qt admin warmup-disable
```

## Documentation

- [QUICKSTART.md](docs/QUICKSTART.md) — 5-min setup
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — diagram + flow detail
- [DEPLOY.md](docs/DEPLOY.md) — VPS production deployment
- [SESSION_STATE.md](docs/SESSION_STATE.md) — context recovery snapshot

## Tests

```bash
uv run pytest -q
uv run mypy --strict src/ scripts/
uv run ruff check src/ tests/ scripts/
```

85 tests, mypy strict 64 source files, ruff clean.

## Lisensi

Personal project — qtradesedu (USER).
