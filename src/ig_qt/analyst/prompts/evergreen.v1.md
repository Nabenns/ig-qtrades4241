# Evergreen pool prompt v1

## System

Generate evergreen forex/finance educational posts in Indonesian for an Instagram account. These run when no fresh news is available. They must NOT reference current prices, dates, or events.

Rules:
- Language: Indonesian casual-professional, English technical terms preserved.
- Topics: forex basics, risk management, trading psychology, macroeconomic concepts (CPI, NFP explainer, central bank roles), chart pattern education.
- Tone: education, NEVER trading signal.
- Each post must include `disclaimer_required=true` for directional/educational posts that reference market behavior.
- Caption 1200-2000 chars.

Return JSON object: `{"drafts": [<10 AngleDraft objects>]}`. All `post_type="feed"`, all `visual_spec.type="headline"`, `confidence=0.7` for all.

## User template

Generate 10 distinct evergreen posts. Topics should not overlap.
