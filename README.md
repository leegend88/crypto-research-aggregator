# Crypto Research Aggregator

Python MVP that collects crypto research posts from RSS feeds, extracts article text,
summarizes each article in Korean with the OpenAI API, and sends the digest to a
Telegram channel. Processed articles are stored in SQLite so the same article is not
sent twice.

## Requirements

- Python 3.11 or newer
- OpenAI API key
- Telegram bot token and target chat/channel ID

## Setup

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-5-mini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=@your_channel_or_chat_id
```

Optional runtime controls:

```env
MAX_ARTICLES_PER_RUN=5
```

Each run stores newly discovered articles, then processes at most
`MAX_ARTICLES_PER_RUN` pending articles. Sources are selected in round-robin
order, while articles within each source remain latest-first, so one high-volume
source cannot occupy the entire run.

## Telegram Setup

1. Create a bot with BotFather and copy the token.
2. Add the bot to your channel or chat.
3. For a public channel, use `@channelname` as `TELEGRAM_CHAT_ID`.
4. For a private chat or channel, obtain the numeric chat ID and use that value.

## RSS Sources

Edit `config/sources.yaml`:

```yaml
sources:
  - name: Example Research
    type: rss
    url: https://example.com/feed
    enabled: true
```

Only enabled RSS sources are collected. The collector interface is isolated so API
collectors can be added later.

Supported source types:

- `rss`: parses RSS/Atom feeds.
- `html_listing`: extracts article links from a public listing page.
- `sitemap`: extracts article URLs from XML sitemaps.

The default config includes 4Pillars Research, Tiger Research Korean, and
CoinMarketCap Community Articles as enabled sources. Binance Research is included
but disabled because its article pages currently return an anti-bot empty response
to requests-based extraction; it should be enabled after adding a browser or
official API-backed extractor.

## Run

Run once:

```bash
python run.py --run-once
```

Run the daily scheduler:

```bash
python run.py
```

The default schedule is 08:00 Asia/Seoul. Change `SCHEDULE_HOUR`,
`SCHEDULE_MINUTE`, and `TIMEZONE` in `.env`.

## GitHub Actions

The workflow in `.github/workflows/daily.yml` runs every day at 08:00
Asia/Seoul and can also be started manually from the Actions tab.

Add these repository secrets under **Settings > Secrets and variables >
Actions**:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optionally add the repository variable `MAX_ARTICLES_PER_RUN`. It defaults to
`5`.

The workflow stores processed article history in `.state/articles.db` and
restores it through the GitHub Actions cache on the next run. A unique cache is
saved after every successful run, and concurrency is limited to one run so two
jobs cannot publish the same article at the same time.

GitHub may remove caches that have not been accessed for an extended period.
For a long-running production deployment, use an external persistent database
instead of the Actions cache.

Telegram messages are sent in this shape:

```text
📌 English original title

핵심 요약

소제목 1
• 해당 문단의 핵심 주장과 근거, 중요한 수치를 구체적으로 요약합니다.
• 인과관계와 비교 기준, 주의할 해석까지 원문에 근거해 설명합니다.

소제목 2
• 다음 문단의 핵심 내용을 원문 순서대로 요약합니다.

🔗 원문 보기
```

Summaries follow the article's section order and the combined section headings
and summaries are limited to 2,000 characters. The summarizer prioritizes
complete sections and sentences so content is not cut mid-thought. Telegram message splitting
remains as a defensive fallback for manually stored content.

## Tests

```bash
pytest
```

## Modules

- `app/config.py`: environment variables and RSS source config
- `app/database.py`: SQLite schema and article status updates
- `app/collectors/rss_collector.py`: RSS feed parsing
- `app/extractors/article_extractor.py`: article text extraction and fallback parsing
- `app/summarizers/openai_summarizer.py`: section-by-section Korean summaries
- `app/publishers/telegram_publisher.py`: Telegram HTML message formatting and sending
- `app/main.py`: end-to-end pipeline orchestration
- `app/scheduler.py`: APScheduler daily run
