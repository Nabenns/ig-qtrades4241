# Architecture — ig-qt

System untuk auto-generate konten Instagram forex/finance edukasi (qtradesedu) — dari fetch berita, generate caption + visual cinematic via AI, sampai review approval workflow di Telegram.

## High-level flow

```mermaid
flowchart LR
    subgraph "Data Sources"
        N1[NewsAPI]
        N2[GNews]
        N3[Forex Factory<br/>Playwright scrape]
        N4[Twelve Data<br/>OHLC prices]
        N5[RSS feeds<br/>ForexLive,<br/>Investing, etc]
    end

    subgraph "Pipeline"
        C[Collector<br/>tiap 15 menit] --> S[(SQLite)]
        S --> A[Analyst<br/>2-stage LLM<br/>tiap 30 menit]
        A --> S
        S --> COMP[Composer<br/>tiap 10 menit]
        COMP --> IG[Image Gen<br/>Cloudflare Flux]
        IG --> CRIT[Critic<br/>Mistral Vision]
        CRIT -.adaptive retry.-> IG
        CRIT --> COMP
        COMP --> S
    end

    subgraph "Review"
        S --> RB[Review Bot<br/>Telegram]
        RB --> USR[User]
        USR --> RB
        RB --> S
    end

    subgraph "Publish"
        S --> PUB[Publisher<br/>tiap 5 menit]
        PUB --> IGAPP[Instagram]
    end

    N1 --> C
    N2 --> C
    N3 --> C
    N4 --> C
    N5 --> C

    style A fill:#5eead4,color:#000
    style IG fill:#5eead4,color:#000
    style CRIT fill:#5eead4,color:#000
    style RB fill:#5eead4,color:#000
```

## Pipeline detail

```mermaid
sequenceDiagram
    participant Cron as APScheduler
    participant Coll as Collector
    participant News as News APIs/RSS
    participant DB as SQLite
    participant Anal as Analyst
    participant LLM as 9router (Claude/Kiro)
    participant Comp as Composer
    participant CF as Cloudflare Flux
    participant Mst as Mistral 3.1
    participant TG as Telegram
    participant User
    participant Pub as Publisher
    participant IG as Instagram

    Cron->>Coll: trigger /15min
    Coll->>News: fetch (parallel)
    News-->>Coll: articles
    Coll->>DB: dedup + insert raw_news

    Cron->>Anal: trigger /30min
    Anal->>DB: load 24h news + events
    Anal->>LLM: rank 5 candidates
    LLM-->>Anal: ranked picks
    Anal->>LLM: generate angle (1 feed + 3 story)
    LLM-->>Anal: drafts (caption, visual_spec, hashtags)
    Anal->>DB: post_drafts (status=pending)

    Cron->>Comp: trigger /10min
    Comp->>DB: load pending drafts
    loop For each draft with hero_image_prompt
        Comp->>CF: generate image
        CF-->>Comp: PNG bytes
        Comp->>Mst: score image (vision)
        Mst-->>Comp: {score, issues, tweak_hint}
        alt score < 0.7 and retries left
            Comp->>CF: regenerate with tweaked prompt
        end
    end
    Comp->>Comp: render Tailwind+Geist HTML +<br/>Playwright screenshot
    Comp->>DB: posts (status=review)

    Cron->>TG: review_send /2min
    TG->>User: photo + caption + buttons<br/>(Approve / Reject / Copy / Regen)
    User->>TG: button click
    Cron->>TG: review_poll /20s
    TG->>DB: update status (approved/rejected)

    Cron->>Pub: trigger /5min
    Pub->>DB: load approved + scheduled
    alt warmup not active and not paused
        Pub->>IG: photo_upload (instagrapi)
        IG-->>Pub: media_id
        Pub->>DB: status=published
    else
        Pub->>Pub: skip (warmup mode)
    end
```

## Data model

```mermaid
erDiagram
    raw_news ||--o{ post_drafts : "source_news_ids"
    post_drafts ||--o{ posts : "draft_id"
    posts ||--|| review_messages : "post_id"
    posts ||--o{ publish_log : "post_id"
    events ||--o{ post_drafts : "context"
    prices_cache ||--o{ post_drafts : "context"

    raw_news {
        int id PK
        string source
        datetime published_at
        text title
        text url
        string dedup_key UK
    }

    events {
        int id PK
        datetime event_time
        string currency
        string name
        string impact
    }

    post_drafts {
        int id PK
        string post_type
        string topic_tag
        text caption_draft
        json visual_spec
        json dynamic_hashtags
        float confidence
        string status
    }

    posts {
        int id PK
        int draft_id FK
        text caption_final
        json hashtags
        text asset_path
        string status
        string ig_media_id
        datetime published_at
    }

    review_messages {
        int id PK
        int post_id FK
        string chat_id
        int message_id
        string decision
        datetime decided_at
    }

    ig_account_state {
        int id PK
        string username
        bool warmup_active
        bool challenge_pending
        datetime pause_until
    }
```

## Post status lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending : Analyst creates draft
    pending --> consumed : Composer picks up
    pending --> rejected : Low confidence (no evergreen)
    consumed --> review : Composer outputs Post

    review --> approved : User clicks Approve in Telegram
    review --> rejected : User clicks Reject in Telegram
    review --> review : User clicks Regenerate (loop)

    approved --> published : Publisher posts to IG
    approved --> failed : IG error / Challenge
    approved --> approved : Skipped (warmup mode)

    failed --> [*]
    published --> [*]
    rejected --> [*]
```

## LLM provider routing

Semua LLM/Image gen jalan via 9router (`http://localhost:20128/v1`) sebagai single point of routing.

```mermaid
flowchart LR
    subgraph "Application"
        AP[ig-qt]
    end

    subgraph "9router (port 20128)"
        OAI["/v1/chat/completions"]
        IMG["/v1/images/generations"]
    end

    subgraph "Upstream Providers"
        K[Kiro AI<br/>free Claude]
        CFP[Cloudflare<br/>Workers AI]
    end

    AP -->|"text generation<br/>(ranker, composer)"| OAI
    AP -->|"vision review<br/>(critic)"| OAI
    AP -->|"image gen"| IMG

    OAI -->|kr/claude-*| K
    OAI -->|cf/@cf/mistralai/<br/>mistral-small-3.1| CFP
    IMG -->|cf/@cf/black-forest-labs/<br/>flux-1-schnell| CFP
```

**Single API key**: `LLM_API_KEY` di `.env` digunakan untuk semua call. Provider routing diatur di 9router dashboard.

## Anti-bot tactics (publisher)

```mermaid
flowchart TD
    PUB[Publisher trigger] --> WIN{Within<br/>posting window<br/>06-23 WIB?}
    WIN -- No --> SKIP1[Skip outside_window]
    WIN -- Yes --> PAUSE{data/PAUSE<br/>file exist?}
    PAUSE -- Yes --> SKIP2[Skip pause_file]
    PAUSE -- No --> WARM{warmup_active<br/>or pause_until<br/>or challenge_pending?}
    WARM -- Yes --> SKIP3[Skip warmup_or_blocked]
    WARM -- No --> SKIP{Skip-day<br/>~14% chance/day<br/>deterministic seed?}
    SKIP -- Yes --> SKIP4[Skip random day]
    SKIP -- No --> RATE{Rate limit<br/>2 feed/day,<br/>5 story/day?}
    RATE -- Over --> SKIP5[Skip rate_limited]
    RATE -- OK --> WARMUP[Pre-warmup:<br/>get_timeline_feed +<br/>random sleep 8-15s]
    WARMUP --> POST[instagrapi.photo_upload]

    POST -->|Challenge| CR[Pause 7 days +<br/>notify Telegram]
    POST -->|Feedback Block| FB[Pause 24h +<br/>backoff]
    POST -->|Login expired| LX[Notify, halt batch]
    POST -->|Success| OK[status=published<br/>+ Telegram notify]

    style WARMUP fill:#5eead4,color:#000
    style OK fill:#34d399,color:#000
    style CR fill:#f87171,color:#000
```

## Service layout (Docker compose)

```mermaid
flowchart LR
    subgraph "Host"
        Compose[docker compose up -d]
    end

    subgraph "Container: ig-qt-router"
        R9[9router Node.js<br/>:20128]
        RD[(router-data/<br/>OAuth tokens)]
    end

    subgraph "Container: ig-qt"
        SCH[Python scheduler]
        SCH_HEALTH[/health :8080/]
        DB[(data/ig_qt.db)]
        FILES[(data/posts/*.jpg)]
        LOG[(data/logs/*.log)]
    end

    Compose --> R9
    Compose --> SCH

    SCH -->|"http://router:20128"| R9
    SCH --> DB
    SCH --> FILES
    SCH --> LOG

    R9 --> RD

    Compose -->|"127.0.0.1:8080"| SCH_HEALTH
    Compose -->|"127.0.0.1:20128"| R9

    style R9 fill:#5eead4,color:#000
    style SCH fill:#5eead4,color:#000
```

## Komponen utama

| Komponen | File | Fungsi |
|---|---|---|
| **Collector** | `collector/pipeline.py` | Orchestrator semua source: NewsAPI, GNews, RSS, Forex Factory, Twelve Data |
| **Analyst Ranker** | `analyst/ranker.py` | Stage 1 LLM: rank 5 kandidat berita berdasarkan impact/recency/diversity |
| **Analyst Angle Gen** | `analyst/angle_generator.py` | Stage 2 LLM: generate caption draft + visual_spec + hashtags |
| **Image Gen** | `composer/image_gen.py` | Cloudflare Flux Schnell via 9router atau direct |
| **Image Critic** | `composer/image_critic.py` | Mistral 3.1 Vision via 9router scoring + tweak hint |
| **Composer** | `composer/runner.py` | Orchestrate hero gen + critic loop + Tailwind HTML render via Playwright |
| **Publisher** | `publisher/runner.py` | instagrapi posting dengan anti-ban tactics |
| **Telegram Reviewer** | `notifier_review.py` | Send + poll review with inline buttons |
| **Scheduler** | `scheduler.py` + `app.py:run_long_running` | APScheduler all jobs |
| **Health Endpoint** | `health.py` | FastAPI `/health` for monitoring |

## Konfigurasi penting

| Setting | Default | Lokasi | Notes |
|---|---|---|---|
| News collection interval | 15 menit | `scheduler.py` | RSS unlimited, NewsAPI 100 req/day = 96 req aman |
| Analyst interval | 30 menit | `scheduler.py` | LLM cost ~$0/day pakai Kiro free tier |
| Composer interval | 10 menit | `scheduler.py` | Pick up pending drafts cepat |
| Publisher interval | 5 menit | `scheduler.py` | Skip kalau warmup mode atau outside window |
| Review send | 2 menit | `scheduler.py` | Telegram-bound |
| Review poll | 20 detik | `scheduler.py` | Telegram callback responsiveness |
| Posting window | 06-23 WIB | `config.yaml` | Jam manusiawi |
| Skip day prob | 14% | `config.yaml` | Anti-bot, 1 hari/minggu |
| Rate limits | 2 feed, 5 story/day | `config.yaml` | Konservatif vs IG soft limit |
| Critic threshold | 0.7 | `composer/runner.py` | Score >= 0.7 = accept |
| Critic max retries | 2 | `composer/runner.py` | Max 3 attempts total |

## Cara development local (tanpa Docker)

```bash
# Terminal 1: 9router
npm install -g 9router
9router

# Terminal 2: ig-qt
uv sync --prerelease=allow
uv run python -m ig_qt --check
uv run python -m ig_qt run
```

Lihat [QUICKSTART.md](QUICKSTART.md) untuk step lebih detail.
