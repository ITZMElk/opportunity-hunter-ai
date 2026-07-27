# Opportunity Hunter AI

Opportunity Hunter AI is a production-ready FastAPI service that aggregates permitted public opportunity feeds, evaluates each new item against an editable student profile with Gemini, and delivers strong matches through Telegram. A responsive Jinja dashboard makes the collected data easy to explore.

## Features

- Official RSS/Atom sources with per-source timeouts, retries, and failure isolation
- Gemini structured JSON analysis with validation and one retry for invalid output
- SQLite locally; Railway/PostgreSQL automatically when `DATABASE_URL` is supplied
- Duplicate protection using a normalized title + organizer hash
- Automatic APScheduler checks every 30 minutes by default
- Telegram MarkdownV2 digests, capped safely below 4096 characters
- Dark, responsive dashboard with search, filtering, sorting, details, and analytics
- Daily rotating application logs in `logs/`

## Architecture

```text
Official RSS/Atom feeds ─┐
                         ├─> source discovery -> dedupe -> Gemini -> PostgreSQL/SQLite
Unstop fixture/API ──────┘                                  │
                                                            ├─> Telegram digest
FastAPI + APScheduler ──────────────────────────────────────┴─> Jinja dashboard
```

## Quick start

Python 3.12 is recommended.

```powershell
cd opportunity-hunter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the dashboard. Trigger an immediate check with:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/run-now
```

## Configuration

Copy `.env.example` to `.env`, then configure the following:

| Variable | Required | Purpose |
|---|---:|---|
| `GEMINI_API_KEY` | Yes | Gemini API key used for scoring |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.0-flash` |
| `DATABASE_URL` | No | PostgreSQL URL in Railway; SQLite fallback when unset |
| `RSS_FEED_URLS` | No | Comma-separated permitted RSS/Atom URLs |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Yes | Telegram destination chat ID |
| `SCHEDULE_INTERVAL_MINUTES` | No | Positive integer; defaults to `30` |
| `LOG_LEVEL` | No | Defaults to `INFO` |
| `STUDENT_PROFILE_PATH` | No | Profile JSON location; defaults to `student_profile.json` |

`SCHEDULE_INTERVAL_HOURS` is also accepted for backward compatibility, but `SCHEDULE_INTERVAL_MINUTES` takes precedence.

### Sources

When `RSS_FEED_URLS` is blank, the app uses these official feeds:

- GitHub Blog: `https://github.blog/feed/`
- Google AI Blog: `https://blog.google/technology/ai/rss/`
- AWS News Blog: `https://aws.amazon.com/blogs/aws/feed/`
- Hugging Face Blog: `https://huggingface.co/blog/feed.xml`
- Google Summer of Code label feed: `https://opensource.googleblog.com/feeds/posts/default/-/Google%20Summer%20of%20Code`
- OpenAI News: `https://openai.com/news/rss.xml`

Each source is independent: a timeout, feed parse error, or HTTP error is logged and does not stop the remaining feeds. MLH currently has no verified official public events RSS/API, so it is deliberately not scraped. The Unstop adapter uses static test data only when `UNSTOP_API_URL` is blank and logs a warning at startup.

To use your own feeds, set for example:

```dotenv
RSS_FEED_URLS=https://example.org/feed.xml,https://www.google.com/alerts/feeds/<FEED_ID>/<ID>
```

For a Google Alert, create an alert such as `student hackathon India` at [Google Alerts](https://www.google.com/alerts), choose **RSS feed** as delivery, and copy its generated feed URL into `RSS_FEED_URLS`.

### Student profile

Edit [student_profile.json](student_profile.json) to change skills, interests, locations, experience, and resume keywords. It is loaded automatically at startup and supplied to Gemini for every analysis.

## Scheduler and logs

The scheduler starts during FastAPI lifespan startup, independently of `/run-now`. At boot it logs `Starting Scheduler`; each execution logs `Running Scheduled Check` and `Finished Scheduled Check`. Inspect terminal output or `logs/opportunity-hunter.log` to verify it.

## Docker

```powershell
docker build -t opportunity-hunter .
docker run --rm -p 8000:8000 --env-file .env opportunity-hunter
```

## Railway deployment

1. Push this directory to GitHub and create a Railway project from that repository.
2. Add a **PostgreSQL** service. Railway provides `DATABASE_URL`; expose it to the web service.
3. Add all required variables from `.env.example` in Railway's Variables tab. Do not upload `.env`.
4. Deploy. `railway.json` directs Railway to use the included Python 3.12 Dockerfile. The container starts Uvicorn using Railway's `PORT`.
5. Open the deployed URL and inspect the deployment logs for `Starting Scheduler`.

Use one Railway web replica. As an extra production safeguard, PostgreSQL deployments use an advisory lock, so a second replica will not start another scheduler. SQLite is intended for single-process local development.

### Telegram setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token to `TELEGRAM_BOT_TOKEN`.
2. Send the bot a message (or add it to the target group), then obtain the numeric chat ID and set `TELEGRAM_CHAT_ID`.
3. Trigger `POST /run-now` after adding a Gemini key to test a digest. Never commit these values.

### PostgreSQL

Railway injects `DATABASE_URL` when the web service is linked to its PostgreSQL service. SQLAlchemy uses PostgreSQL automatically; without that variable, it uses the local SQLite file. Tables are created at startup.

### Health endpoint

Railway can probe `GET /health`. A healthy deployment returns:

```json
{"status":"ok","scheduler":"running","database":"connected","rss_sources":6}
```

`rss_sources` reflects the configured RSS/Atom URL count, so it can differ from `6` when `RSS_FEED_URLS` is explicitly set. If a PostgreSQL scheduler lock is held by another replica, that replica reports `scheduler: "stopped"` and does not run duplicate jobs.

## Testing checklist

```powershell
pytest tests -q
```

- Dashboard returns HTTP 200 at `/`
- `/run-now` runs safely with missing external credentials (it logs skipped analysis)
- A PostgreSQL Railway deployment creates tables automatically
- Scheduler log shows the configured interval and future next-run timestamp
- Telegram delivery is verified after setting bot credentials and chat ID

## Project structure

```text
app/
  pipeline/       # dedupe, Gemini analysis, rank, notification, orchestration
  sources/        # drop-in registered source adapters
  templates/      # Jinja dashboard pages
  static/         # responsive dark-mode CSS
  dashboard.py    # dashboard routes and analytics
  scheduler.py    # APScheduler lifecycle
```

## Screenshots

_Add dashboard and Telegram screenshots here after deploying your personalized instance._

## Roadmap

- Per-user profiles and authenticated accounts
- Postgres migrations through Alembic
- Queue-backed scheduled workers for horizontal scaling
- Saved searches and source health monitoring
