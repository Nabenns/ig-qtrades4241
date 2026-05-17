# IG Forex Automation — Design Spec

- **Project:** ig-qt
- **Created:** 2026-05-17
- **Status:** Approved (pending implementation plan)
- **Owner:** USER

## 1. Goal

Bangun sistem otomatis penuh untuk akun Instagram bertema forex / finance / kondisi makro global. Sistem mengumpulkan berita & data pasar, menganalisis dengan LLM, menghasilkan caption + visual, dan posting ke Instagram (1 feed/hari + 2–3 story/hari) tanpa intervensi manual sehari-hari.

**Non-goals (sekarang):**
- Multi-akun (single akun dulu).
- Posting Reels (video).
- Auto-reply DM / komentar.
- Konten signal trading (BUY/SELL eksplisit) — hanya edukasi & market context.

## 2. Constraints & Decisions Locked

| Topik | Pilihan |
|---|---|
| Level otomatisasi | Full-auto (generate + post tanpa human review per-post) |
| Sumber data | Free-tier mix: NewsAPI + GNews + Twelve Data + Forex Factory scrape + yfinance backup |
| Format konten | Feed post (single image) + Story (3 jenis: event reminder, market update, EOD recap) |
| Frekuensi | 1 feed/hari (pre-London ~11:00 WIB) + 2–3 story/hari |
| Posting method | instagrapi (unofficial API) — risk-aware, dengan mitigasi |
| Stack | Python 3.12 + SQLite + APScheduler |
| Hosting | VPS (target Contabo VPS S 4 vCPU / 8 GB atau Hetzner CX22 2 vCPU / 4 GB) |
| LLM | Provider-agnostic; default 9router kalau OpenAI-compatible, fallback OpenAI/Anthropic/Gemini direct |
| Visual | Hybrid: template HTML+CSS via Playwright screenshot **+** real chart via mplfinance |
| Scraping | Playwright headless (Forex Factory + ForexLive opsional) |
| Arsitektur | Pipeline linear sederhana, satu service, satu DB |

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ig-qt (Python service)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │collector │→ │ analyst  │→ │ composer │→ │  publisher  │ │
│  │ (news,   │  │ (LLM:    │  │(caption  │  │ (instagrapi │ │
│  │ prices,  │  │ rank,    │  │ + visual │  │  feed/story)│ │
│  │ events)  │  │ angle)   │  │ render)  │  │             │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘ │
│       ▼             ▼             ▼                ▼        │
│  ┌────────────────────────────────────────────────────┐    │
│  │  SQLite (raw_news, events, post_drafts, posts,      │    │
│  │  publish_log, prices_cache, ig_account_state, ...)  │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌──────────────┐         ┌──────────────────────────┐    │
│  │ APScheduler  │ ──────→ │  LLM provider (abstract) │    │
│  │  (cron jobs) │         │  9router / OpenAI / etc  │    │
│  └──────────────┘         └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
External:
  • NewsAPI / GNews                • Twelve Data (prices)
  • Forex Factory (Playwright)     • Instagram (instagrapi)
  • Telegram (notifications)
```

**Modul utama:**
1. **collector** — fetch berita, harga, event ekonomi → simpan terstruktur ke SQLite.
2. **analyst** — LLM rank berita + pilih angle posting → tulis ke `post_drafts`.
3. **composer** — finalisasi caption + render visual (chart atau template HTML) → tulis ke `posts` dengan asset path.
4. **publisher** — ambil post yang ready & waktunya tepat, post ke IG via instagrapi → log ke `publish_log`.
5. **scheduler** — APScheduler in-process, jobstore persistent di SQLite, dengan jitter random.
6. **notifier** — Telegram bot untuk alert (challenge required, failed publish, dry day, dll).
7. **health** — FastAPI mini `/health` endpoint untuk UptimeRobot.

## 4. Data Sources & Collector

### 4.1 Sumber

| Source | Apa | Limit | Strategy |
|---|---|---|---|
| NewsAPI.org (free) | Headline finance | 100 req/hari, 24h delay | 1× pagi (~10:00 WIB), filter business + keyword forex/USD/EUR/Fed |
| GNews (free) | Headline real-time | 100 req/hari | 2× sehari (pagi + sore), source utama, jitter ±15 menit |
| Twelve Data (free) | Harga forex pairs (EUR/USD, GBP/USD, USD/JPY, XAU/USD, DXY, BTC/USD) | 800 req/hari, 8/menit | On-demand saat composer butuh chart, cache 5 menit |
| Forex Factory | Calendar event ekonomi (impact level) | Tidak ada API resmi | **Playwright headless**, 1× Senin pagi, ambil 7 hari ke depan |
| ForexLive (opsional, Phase 2) | Headline real-time tambahan | — | Playwright 2× sehari |
| yfinance | Backup harga + DXY/SPX/gold | Unofficial, no key | Fallback kalau Twelve Data quota habis |

### 4.2 Modul

```
collector/
  base.py             # BaseSource: fetch() → list[NormalizedItem]
  news_api.py
  gnews.py
  twelve_data.py
  forex_factory.py    # Playwright
  yfinance_src.py     # backup
  playwright_runner.py  # shared browser_session() context manager
  pipeline.py         # orchestrator dengan try/except per source
```

`NormalizedItem` schema: `source`, `external_id`, `published_at`, `title`, `summary`, `url`, `keywords`, `raw_payload`.

### 4.3 Playwright runner (shared)

```python
@asynccontextmanager
async def browser_session():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=random.choice(UA_POOL),
            timezone_id="Asia/Jakarta",
            locale="en-US",
        )
        try: yield ctx
        finally: await browser.close()
```

VPS requirements: Chromium binary via `playwright install chromium` + OS deps via `playwright install-deps chromium`. Headless mode tidak butuh X11.

### 4.4 Deduplication

- Hash `(normalized_title, published_date)` → `dedup_key` UNIQUE.
- `INSERT OR IGNORE` di SQLite.
- Levenshtein similarity check (<0.15) saat select untuk analyst.

### 4.5 Rate limit & politeness

- Exponential backoff 429.
- `time.sleep(random.uniform(2, 5))` antar request scrape.
- Realistic UA pool (5 entry, rotated).

### 4.6 Tabel terkait

```sql
raw_news (
  id, source, external_id, published_at, title, summary, url,
  keywords (JSON), raw_payload (JSON), dedup_key UNIQUE, created_at
)
events (
  id, source, event_time, country, currency, name, impact,
  forecast, previous, actual, dedup_key UNIQUE
)
prices_cache (
  id, symbol, timeframe, fetched_at, ohlc_json
)
```

## 5. Analyst (LLM Ranking + Angle)

### 5.1 Input per run

- `raw_news` 24 jam terakhir (max 30 item, dedup).
- `events` 24 jam ke depan (impact High/Medium).
- Snapshot harga D1 close untuk pair major.
- `posted_topics` 7 hari terakhir (untuk dedup angle).

### 5.2 Two-stage prompting

**Stage 1 — Ranker (cheap model):** return JSON top-5 by `relevance_score` 0–1.

```json
{ "ranked": [
  {"id": 142, "score": 0.91, "reason": "Fed minutes hawkish, USD impact tinggi"},
  ...
]}
```

Kriteria scoring: impact ke major pairs, recency (<12 jam boost), diversity vs 7 hari terakhir, avoid duplicate angle.

**Stage 2 — Angle generator (quality model):** untuk top-1 (feed) + top-3 (story queue), generate draft per item.

```json
{
  "post_type": "feed",
  "topic_tag": "fed_minutes_hawkish",
  "angle": "Apa artinya Fed hawkish buat USD/JPY",
  "key_points": ["...", "...", "..."],
  "caption_draft": "...",
  "visual_spec": {
    "type": "chart",
    "symbol": "USD/JPY",
    "timeframe": "4H",
    "annotations": ["158 break", "160 target"],
    "headline": "Fed Hawkish, USD/JPY Bidik 160?"
  },
  "disclaimer_required": true,
  "confidence": 0.85
}
```

### 5.3 Tone & guardrails (system prompt)

- Tone: edukasi, bukan signal. Larang "BUY/SELL", "pasti naik", "guaranteed profit".
- Akurasi: angka yang muncul harus dari `events` atau `prices_cache`. Kalau tidak ada → omit.
- Bahasa: Indonesia santai-profesional, mix istilah teknis EN tanpa diterjemahkan.
- Hashtag dari pool curated, max 15.
- Flag `disclaimer_required=true` untuk post directional → composer auto-append.

### 5.4 Provider abstraction

```python
# llm/base.py
class LLMProvider(Protocol):
    async def complete_json(self, system: str, user: str, schema: dict) -> dict: ...

# llm/router_9.py, openai_provider.py, anthropic_provider.py, gemini_provider.py
# llm/factory.py — build provider from config
```

Config:
```yaml
llm:
  provider: 9router
  base_url_env: LLM_BASE_URL
  api_key_env: LLM_API_KEY
  models:
    ranker: kr/gemini-flash-2     # cheap
    composer: kr/claude-sonnet-4  # quality
```

### 5.5 Cost estimate

- Ranker: ~5K in + 500 out × 1×/hari × 30 ≈ $0.50/bulan (Sonnet pricing).
- Composer: ~3K in + 2K out × 4 post/hari × 30 ≈ $5/bulan.
- **Total LLM ≈ $5–7/bulan** (lebih murah kalau ranker pakai Gemini Flash / GPT-4o-mini).

### 5.6 Tabel

```sql
post_drafts (
  id, post_type (feed|story), source_news_ids (JSON), topic_tag,
  angle, key_points (JSON), caption_draft, visual_spec (JSON),
  disclaimer_required, confidence,
  llm_provider, llm_model, prompt_version,
  status (pending|approved|rejected|consumed),
  created_at, scheduled_for
)
posted_topics ( topic_tag, last_posted_at )
```

### 5.7 Error handling

- LLM timeout (30s) → retry 2× exponential.
- JSON malformed → structured-output mode atau "fix this JSON" retry.
- Semua draft confidence < 0.6 → fallback **evergreen content pool** (post edukasi pre-generated, no live data).
- 3 hari berturut analyst gagal → notif Telegram, pause auto-publish.

## 6. Composer

### 6.1 Pipeline

```
post_drafts(pending)
  → caption_finalizer (polish, disclaimer, hashtag, CTA, replace placeholders)
  → visual_router by spec.type
       ├─ chart       (mplfinance)
       ├─ headline    (HTML+Playwright)
       ├─ event       (HTML+Playwright)
       └─ market_recap(HTML+Playwright)
  → postprocess (resize, watermark, sRGB, JPEG q92)
  → write asset to data/posts/<post_id>/{feed.jpg|story.jpg}
  → insert posts (status=ready)
```

### 6.2 Visual rendering

**A. Chart (mplfinance):**
- Style custom (dark BG, brand color), candlestick + EMA20/50, S/R lines dari annotations.
- Output 1080×1080 (feed) atau 1080×1920 (story).

**B. Headline / Event / Recap card (Playwright + Jinja2):**
- Template HTML di `templates/`, brand vars dari `config.yaml` (color, font, logo, handle).
- `set_content(html, wait_until="networkidle")` → `screenshot(full_page=False)` dengan viewport sesuai output.

### 6.3 Story-specific

- **Story 1 (siang ~12:00 WIB):** event reminder hari ini → `event_card.html`.
- **Story 2 (sore opsional):** mid-day market update.
- **Story 3 (malam ~21:00 WIB):** EOD recap 4 pair major → `market_recap.html`.

Story tidak butuh LLM mahal: composer pakai template + data live + caption pendek (50–100 chars).

### 6.4 Post-processing (Pillow)

- Resize 1080×1080 (feed) atau 1080×1920 (story).
- Watermark logo + handle bottom-right.
- Convert RGB (no alpha), JPEG quality 92, optimize.
- Hard cap 8 MB; kalau lewat, re-compress quality 85.

### 6.5 Tabel

```sql
posts (
  id, draft_id (FK), post_type, caption_final, hashtags (JSON),
  asset_path, visual_type (chart|headline|event|recap),
  scheduled_for, status (ready|published|failed),
  ig_media_id, published_at, error_log, created_at
)
```

### 6.6 Error handling & fallback chain

- mplfinance gagal (data <50 candle) → fallback `headline_card`.
- Playwright timeout render → retry 1× → fallback Pillow plain text card.
- Image >8 MB → re-compress.
- Total fail → status `failed`, skip publish, notif.

## 7. Publisher + Scheduler

### 7.1 Session management

- instagrapi `Client.load_settings(session.json)` di setiap startup.
- Validate dengan `get_timeline_feed()` ringan; kalau `LoginRequired` → re-login 1× → kalau gagal lagi → notif & pause.
- **Device fingerprint stabil** — jangan regenerate.
- Backup `data/ig_session.json` daily ke storage offsite (Backblaze B2 / Hetzner Storage Box).

### 7.2 Anti-ban tactics (CRITICAL)

| Tactic | Implementasi |
|---|---|
| Jitter timing | APScheduler `jitter=900` (±15 menit), eksekusi tidak pernah jam bulat |
| Delay built-in | `client.delay_range = [2, 5]` |
| Manual sleep | `time.sleep(random.uniform(8, 15))` sebelum upload |
| Pre-warmup | `get_timeline_feed()` + 1–2 explore page sebelum post |
| Skip day | ~14% probability/hari (deterministic by date hash) → ~1×/minggu skip feed |
| Variasi caption opening | Pool 20+ opener berbeda |
| Posting window | 06:00–23:00 WIB only |
| Stop on challenge | `ChallengeRequired` → `pause_until = +7 hari`, notif, tunggu manual resolve |

### 7.3 Hard rate limits (jauh di bawah IG)

| Type | Limit |
|---|---|
| Feed post | 2/hari, 10/minggu |
| Story | 5/hari |
| Login attempt | 1/hari |

Cek `ig_account_state` sebelum publish.

### 7.4 Posting flow

**Feed:**
```python
pre_warmup()
await asyncio.sleep(random.uniform(8, 15))
media = ig.cl.photo_upload(path=post.asset_path, caption=post.caption_final)
update_post(post.id, status="published", ig_media_id=media.pk)
```

**Story:**
```python
pre_warmup()
await asyncio.sleep(random.uniform(5, 10))
story = ig.cl.photo_upload_to_story(path=post.asset_path, links=...)
```

### 7.5 APScheduler setup

```python
scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url="sqlite:///data/jobs.db")},
    timezone="Asia/Jakarta",
)

scheduler.add_job(collector.fetch_news,    "cron", hour=9,  jitter=900, id="news_morning")
scheduler.add_job(collector.fetch_news,    "cron", hour=18, jitter=900, id="news_evening")
scheduler.add_job(collector.fetch_calendar,"cron", day_of_week="mon", hour=7, jitter=1800, id="ff_calendar")
scheduler.add_job(analyst.run_daily,       "cron", hour=11, jitter=900, id="analyst_daily")
scheduler.add_job(composer.process_pending,"interval", minutes=15, id="composer_loop")
scheduler.add_job(publisher.run_due,       "interval", minutes=5,  id="publisher_loop")
scheduler.add_job(stories.event_reminder,  "cron", hour=12, jitter=600, id="story_event")
scheduler.add_job(stories.market_recap,    "cron", hour=21, jitter=900, id="story_recap")
```

### 7.6 Failure handling

| Error | Action |
|---|---|
| `LoginRequired` | Re-login 1×; gagal → pause + notif |
| `ChallengeRequired` | `pause_until = +7d`, notif, manual resolve |
| `FeedbackRequired` ("action blocked") | `pause_until = +24h`, exponential backoff |
| `PleaseWaitFewMinutes` | Sleep 5–15 menit, retry sekali |
| Network error | Retry 3× exponential |
| `MediaNotFound` post-upload | Treat as success (race condition) |

### 7.7 Kill switch & notifications

- File `data/PAUSE` exist → publisher skip semua. Toggle via SSH.
- Telegram bot alert untuk: challenge required, 3× failed publish berturut, dry day analyst, session need re-login.

### 7.8 Tabel

```sql
publish_log (
  id, post_id, ig_media_id, ig_account_pk, attempt_no,
  status (success|failed|challenge), error_type, error_message,
  attempted_at, took_ms
)
ig_account_state (
  id, username, last_login_at, last_post_at,
  challenge_pending (bool), pause_until,
  daily_post_count, weekly_post_count
)
```

## 8. Project Structure

```
ig-qt/
├── pyproject.toml              # uv, Python 3.12+
├── README.md
├── .env.example
├── .gitignore                  # data/, *.session, .env
├── docker-compose.yml
├── Dockerfile
├── config.yaml
├── src/ig_qt/
│   ├── __main__.py
│   ├── app.py
│   ├── config.py               # Pydantic Settings
│   ├── db.py
│   ├── models.py               # SQLAlchemy
│   ├── collector/...
│   ├── analyst/...
│   │   └── prompts/
│   │       ├── ranker.v1.md
│   │       └── composer.v1.md
│   ├── composer/...
│   ├── publisher/...
│   ├── llm/...
│   ├── scheduler.py
│   ├── notifier.py
│   └── health.py
├── templates/
│   ├── base.css
│   ├── headline_card.html
│   ├── event_card.html
│   └── market_recap.html
├── assets/
│   └── logo.png
├── data/                       # gitignored
│   ├── ig_qt.db
│   ├── jobs.db
│   ├── ig_session.json         # BACKUP
│   ├── posts/<post_id>/feed.jpg
│   ├── logs/
│   └── PAUSE                   # kill switch
├── scripts/
│   ├── ig_login_first_time.py
│   ├── backup_session.sh
│   └── migrate.py
└── tests/
```

## 9. Configuration

**`config.yaml` (committed, non-secret):** brand vars, LLM provider/models, schedule hours+jitter, IG limits, collector source toggles.

**`.env` (gitignored, secrets only):** `LLM_BASE_URL`, `LLM_API_KEY`, `IG_USERNAME`, `IG_PASSWORD`, `NEWSAPI_KEY`, `GNEWS_KEY`, `TWELVEDATA_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

Pydantic Settings load both, validate at startup, fail-fast jika ada missing.

## 10. Deployment

### 10.1 Dockerfile (ringkasan)

- Base `python:3.12-slim`.
- Install OS deps untuk Playwright (libnss3, libatk, libcairo, fonts-liberation, dll) + libjpeg/zlib untuk Pillow.
- `uv sync --frozen --no-dev`.
- `uv run playwright install chromium`.
- `VOLUME ["/app/data"]`, expose 8080 (health).
- CMD: `uv run python -m ig_qt`.

### 10.2 docker-compose.yml

- Single service `ig-qt`, `restart: unless-stopped`.
- Mount `./data:/app/data` + `./config.yaml:ro`.
- Bind `127.0.0.1:8080:8080` (health endpoint, localhost only).
- Healthcheck `curl /health`.

### 10.3 First-time login

```bash
docker compose run --rm ig-qt python scripts/ig_login_first_time.py
# Interactive: handle ChallengeRequired (kode email), simpan session.json
```

### 10.4 Update flow

```bash
git pull && docker compose build && docker compose up -d
```

### 10.5 Backup

- Cron VPS daily: `rsync data/ig_qt.db data/ig_session.json` ke Backblaze B2 / Storage Box.

## 11. Observability

| Layer | Tool |
|---|---|
| App logs | Loguru → JSON file, rotate 100 MB / 30 hari |
| Errors | Separate `errors.log`, retain 90 hari |
| Health | FastAPI `/health` (last_post_at, pause_until, pending counts, last_error) |
| Uptime | UptimeRobot ping `/health` (free) |
| Alerts | Telegram bot |
| Metrics | SQL on demand (post count, LLM cost) |
| Optional | Sentry free tier |

**Log content rules:** secrets never logged (Pydantic SecretStr); caption final selalu logged untuk audit; LLM cost per call tracked.

## 12. Cost Estimate (monthly)

| Item | USD |
|---|---|
| VPS Contabo VPS S (4 vCPU, 8 GB) atau Hetzner CX22 (2 vCPU, 4 GB) | ~$6 |
| LLM (9router atau direct) | $2–7 |
| NewsAPI / GNews / Twelve Data free | $0 |
| Backblaze B2 backup | ~$1 |
| UptimeRobot, Sentry free, Telegram | $0 |
| **Total** | **~$9–14** |

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| IG flag/ban akun (instagrapi) | Session persistence, jitter, pre-warmup, skip day, hard rate limit, kill switch, pause-on-challenge |
| LLM hallucinate angka finansial | Composer hanya pakai angka dari `prices_cache`/`events`; placeholder substitution; disclaimer required untuk directional post |
| Forex Factory ubah HTML | Playwright + selector test; alert kalau parse return 0 events; fallback ke ekonomi calendar source lain (Phase 2) |
| Free tier API quota habis | Backup source (yfinance untuk price, GNews+NewsAPI saling backup); evergreen content fallback |
| VPS down / disk corrupt | Daily offsite backup `ig_qt.db` + `ig_session.json`; restore = lanjut tanpa re-login |
| Repetitive content | `posted_topics` dedup 7 hari + diversity scoring di ranker + variasi opener pool |
| Konten misleading | Disclaimer auto-append; tone "edukasi bukan signal"; manual review periodic via SQL query |

## 14. Open Questions / Phase 2

- 9router API endpoint OpenAI-compatible? **Cek saat implementasi**, design sudah provider-agnostic.
- Reels (video) generation — defer ke Phase 2.
- Multi-akun support — defer, refactor minor saat dibutuhkan.
- Comment/DM auto-reply — defer.
- A/B testing prompt versions — `prompt_version` field sudah ada di tabel, tooling defer.

## 15. Success Criteria

- 30 hari pertama tanpa ban / challenge yang gak ke-resolve.
- Konsistensi posting: ≥25 feed post / 30 hari (toleransi skip day + dry day).
- Akurasi data: zero post dengan angka harga/event yang salah (audit manual mingguan, target 0).
- Cost real ≤ $15/bulan.
- Mean time to recovery dari challenge ≤ 24 jam (manual).
