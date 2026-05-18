# ig-qt — Session State Snapshot (2026-05-18)

## Project status: 100% feature-complete, currently iterating on visual quality + agentic loop

**Repo:** https://github.com/Nabenns/ig-qtrades4241
**Latest commit:** `3f00d2e feat(image-gen): route via 9router /v1/images/generations for centralized image gen`
**Tests:** 85 passing, mypy strict 58 files clean, ruff clean
**CLI:** `check`, `collect`, `analyze`, `compose`, `run`, `admin warmup-{status,enable,disable}`

## Brand: qtradesedu

- Logo: `assets/logo.png` (gradient teal Q + arrow)
- Handle: `@qtradesedu`
- Account: `benss_workshop` (di .env, akun baru — warmup mode aktif)
- Color palette: dark forest `#06100E` + mint/teal `#5eead4` + coral `#f87171`

## Stack

- Python 3.12 + uv (path: `C:\Users\USER\AppData\Roaming\Python\Python314\Scripts\uv.exe`)
- Working dir: `C:\Users\USER\gt\ig-qt`
- Sources: NewsAPI + GNews + Twelve Data + Forex Factory (Playwright headless)
- LLM: 9router (`http://localhost:20128/v1`), default model `kr/claude-sonnet-4.5` di config.yaml
- DB: SQLite + SQLAlchemy
- Visual: Tailwind CDN + Geist font (Google Fonts) + Playwright screenshot @ device_scale_factor=2
- Image gen: 9router `/v1/images/generations` → Cloudflare Workers AI Flux Schnell

## .env credentials (sudah diisi user — perlu rotate setelah selesai testing)

> Values redacted from this snapshot. See actual `.env` file (gitignored) for current values.

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

- **Kiro AI** (LLM): `kr/claude-opus-4.7`, `kr/claude-sonnet-4.5`, `kr/glm-5`, dll
- **Cloudflare** (image gen): connected as `qt_image_gen` connection. Format key yang work: `<account_id>:<api_token>` (digabung dengan kolon). Model: `cf/@cf/black-forest-labs/flux-1-schnell`

## What's been built (confirmed working)

1. Full pipeline collect → analyze → compose → publish (instagrapi gated by warmup mode)
2. 9router OpenAI-compatible adapter (`Router9Provider`) — `stream: false` + markdown fence stripping
3. Image gen via 9router `/v1/images/generations` (test berhasil, generate 420KB PNG bitcoin coin dramatic)
4. Templates baru pakai Geist + Tailwind CDN + dark forest design language matching reference CW (CoinWatch) IG style
5. VisualSpec schema dengan field-field rich: `big_number`, `stats`, `quote`, `insight`, `hero_image_prompt`, `highlight_phrase`, `highlight_color`
6. Composer prompt v1 sudah include guidance buat semua field termasuk `news_hero` type + `hero_image_prompt`

## Issue yang sedang di-debug saat session jeda

User minta agentic loop:
> "Opus nyari news → Opus generate hero_image_prompt → Cloudflare gen image → Opus liat hasil image (vision) → review bagus/kureng → kalau kureng tweak prompt regenerate (max retry adaptive berdasarkan score Opus)"

**Multimodal vision via 9router gagal:**
- Endpoint `/v1/chat/completions` dengan `image_url` content type → 400 Improperly formed request
- Endpoint `/v1/chat/completions` dengan Anthropic `image source.type=base64` → 400
- Endpoint `/v1/messages` dengan Anthropic native format → 400

Error dari Kiro upstream: `kiro/claude-opus-4.7 [400] Improperly formed request`

**Hipotesis:**
1. Mungkin Kiro tier punya restriction di vision input (test/OAuth limit)
2. Atau format payload via 9router gak proper passthrough untuk multimodal
3. Atau model kr/claude-opus-4.7 di Kiro free tier emang gak support image input

**Yang perlu dicek setelah compact:**
1. Coba model lain yang explicit support vision: `kr/claude-haiku-4.5` (image-capable per Kiro docs)
2. Atau model Sonnet via OAuth subscription (cc/ prefix kalau user punya Claude Code)
3. Atau test direct ke Anthropic via API key (provider `anthropic` di 9router) bukan via Kiro
4. Worst case: skip multimodal vision, pakai heuristic auto-retry (file size check, prompt rotation)

## Files yang sudah modified/added recently

```
assets/logo.png                                  # qtradesedu logo (replaced placeholder)
config.yaml                                       # added image_gen section (provider: router_9, model: cf/@cf/...)
.env.example                                      # added CF_ACCOUNT_ID, CF_API_TOKEN
templates/_base.html                              # NEW — Tailwind + Geist base layout
templates/headline_card.html                      # rebuilt with dark forest + mint accent
templates/event_card.html                         # rebuilt
templates/market_recap.html                       # rebuilt
templates/news_breaking.html                     # NEW — CW-style hero image bg + headline overlay
src/ig_qt/composer/image_gen.py                   # NEW — Router9ImageGen + CloudflareImageGen + ImageGenerator Protocol
src/ig_qt/composer/html_renderer.py               # base64 logo, hero_image_path support, build_headline_html with highlight
src/ig_qt/composer/postprocess.py                 # removed Pillow watermark (HTML now self-contained), 1080x1350 portrait
src/ig_qt/composer/runner.py                      # _maybe_generate_hero, news_hero template path, image_gen integration
src/ig_qt/analyst/schemas.py                      # added hero_image_prompt, highlight_phrase, highlight_color, news_hero type, null-coerce validators
src/ig_qt/analyst/prompts/composer.v1.md          # rewrote with news_hero guidance + hero prompt examples
src/ig_qt/analyst/angle_generator.py              # verbose error logging (preview field)
src/ig_qt/llm/router_9.py                         # stream:false explicit + strip code fence
src/ig_qt/config.py                               # ImageGenConfig with provider/model fields, dotenv auto-load
src/ig_qt/app.py                                  # build_image_gen wired in compose + run, support both router_9 + cloudflare provider
scripts/reset_compose.py                          # NEW — reset drafts ke pending, clear posts dir
data/test_hero.png                                # test image gen output (420KB, golden bitcoin dramatic)
```

## Yang bisa dilanjutin setelah compact

**Pilihan A (lanjut agentic loop):**
1. Cek model yang support vision di Kiro: `uv run python -c "import httpx; r = httpx.get('http://localhost:20128/v1/models', headers={'Authorization': 'Bearer <LLM_API_KEY>'}); print(r.json())"`
2. Try dengan model haiku: `kr/claude-haiku-4.5` (kemungkinan support vision)
3. Atau enable `anthropic` provider di 9router pakai API key langsung (kalau user punya)
4. Implement `image_critic.py` — Claude vision call yang return `{score: 0-1, feedback: str}` based on image
5. Wrap composer.runner._maybe_generate_hero dalam loop adaptif

**Pilihan B (simpler — tanpa vision):**
1. Skip multimodal vision agent
2. Implement heuristic auto-retry: cek file size, prompt rotation, max 2 retry
3. Ship yang ada sekarang ke production

## Test commands cheat sheet

```powershell
# Set PATH (terminal baru perlu re-set)
$env:Path = "C:\Users\USER\AppData\Roaming\Python\Python314\Scripts;$env:Path"

# Smoke check
uv run python -m ig_qt --check

# Reset state + run pipeline
uv run python scripts/reset_compose.py
uv run python -c "import sqlite3; c = sqlite3.connect('data/ig_qt.db'); c.execute('DELETE FROM post_drafts'); c.commit()"
uv run python -m ig_qt analyze
uv run python -m ig_qt compose

# Test image gen direct
uv run python -c "import httpx; r = httpx.post('http://localhost:20128/v1/images/generations', headers={'Authorization': 'Bearer <LLM_API_KEY>', 'Content-Type': 'application/json'}, json={'model': 'cf/@cf/black-forest-labs/flux-1-schnell', 'prompt': 'a dramatic bitcoin coin', 'response_format': 'b64_json'}, timeout=90); print('status:', r.status_code)"

# Verify
uv run pytest -q
uv run mypy --strict src/ scripts/
uv run ruff check src/ tests/ scripts/
```

## Reminder buat user setelah testing selesai

- Rotate IG password (di chat history dengan AI)
- Rotate Telegram bot token via @BotFather
- Rotate Cloudflare API token (Cloudflare dashboard → My Profile → API Tokens → Roll)
- Rotate 9router API key (dashboard → API Keys)
- **Penting**: jangan paste secret di file documentation di repo, gunakan placeholder/redaction
