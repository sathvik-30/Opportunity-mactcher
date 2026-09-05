# OpportunityMatch

OpportunityMatch is a full-stack web app that matches college students to internships, jobs, hackathons, scholarships, and research programs based on their skills, branch, year, and CGPA. Opportunities are scraped automatically from external sources, scored against each student's profile with a TF-IDF matching engine, and surfaced through a dashboard with filtering, saved listings, notifications, and an AI career advisor chatbot.

It's built for students who want a single place to see which live opportunities they actually qualify for, ranked by relevance, instead of manually cross-checking eligibility criteria across many sites.

## Features

- **Authentication** — email/password registration and login with JWT sessions (24-hour expiry), rate-limited (5 requests/minute) against brute-force and spam, plus session restoration on page refresh via `GET /me`.
- **Skill-based matching engine** — TF-IDF + cosine similarity between a student's skills and each opportunity's required skills, producing a 0–100 match score per opportunity.
- **Eligibility checking** — automatic pass/fail checks against each opportunity's minimum year, allowed branches, and minimum CGPA, shown alongside the match score.
- **Editable profile with instant re-matching** — updating name, branch, year, CGPA, or skills persists to the database and recomputes matches immediately.
- **Saved opportunities** — save/unsave any opportunity for later; persisted per-user in the database.
- **Notifications** — students are notified when a newly scraped opportunity crosses their match-score threshold; notifications can be listed, marked read (individually or all at once), or deleted.
- **Automatic background scraping** — a scheduler (APScheduler) periodically runs scrapers against external sources (currently the National Scholarship Portal and SimplifyJobs' internship/new-grad listings) and deduplicates results by normalized URL and content hash.
- **AI career advisor chatbot** — a chat interface backed by Groq (`openai/gpt-oss-20b`), proxied entirely through the backend so the API key never reaches the browser; can discuss listed opportunities and help draft cover letters.
- **Email notifications** — optional SMTP-based email alerts for new matches (disabled by default; the app only logs what it would send until `EMAIL_ENABLED=true` is set).
- **Filtering and sorting** — filter opportunities by type, and sort by match score, deadline, or newest.
- **Admin dashboard** — a separate, admin-only set of endpoints for system statistics, paginated user/opportunity/scraper/notification/email views, and manually triggering a scrape.

## Tech Stack

### Backend
- **FastAPI** (0.141.1) — web framework
- **Uvicorn** — ASGI server
- **Pydantic** (2.13.4) — request/response validation
- **SQLAlchemy** (2.0.52) — ORM
- **SQLite** (via `aiosqlite`) — database
- **passlib + bcrypt** (pinned `bcrypt==3.2.2` for passlib 1.7.4 compatibility) — password hashing
- **python-jose** — JWT signing/verification
- **slowapi** — rate limiting on `/login` and `/register`
- **scikit-learn** — TF-IDF vectorization and cosine similarity for matching
- **httpx** — outbound HTTP (scrapers, Groq proxy)
- **BeautifulSoup4 + lxml** — HTML parsing for scrapers
- **APScheduler** — scheduled background scraping jobs

Exact versions aren't pinned in `requirements.txt` (except `bcrypt`); the versions above are what's currently installed in this project's virtual environment.

### Frontend
- **React** (^19.2.6)
- **Vite** (^8.0.12) — dev server and build tool
- **Axios** (^1.17.0) — HTTP client
- **ESLint** (^10.3.0) — linting

## Architecture

The frontend (React, served by Vite on port 5173 in development) talks to the backend (FastAPI, served by Uvicorn on port 8000) entirely over HTTP/JSON via `axios`/`fetch`, using the base URL from `VITE_API_URL`. The backend is stateless per-request; identity comes from a JWT bearer token issued at login/register and validated on every protected route — the API never trusts a user ID supplied in a request body. The backend also proxies the AI advisor's calls to Groq's API so no third-party key is ever exposed to the browser.

The backend reads from and writes to a single SQLite database file (`backend/data/opportunity_matcher.db`) through SQLAlchemy. A background scheduler process, running inside the same FastAPI process, periodically scrapes external opportunity sources, deduplicates and inserts new listings into that same database, and triggers notification records for matching students — no separate worker process or message queue is involved.

```
opportunity-matcher/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, CORS, route registration
│   │   ├── config.py          # all environment variables read here
│   │   ├── database/          # SQLAlchemy engine, ORM models, migrations
│   │   ├── models/             # Pydantic request/response schemas
│   │   ├── routes/            # auth, matching, users, saved, notifications, admin, chat
│   │   ├── services/           # auth, matching engine, notifications, email, scraping helpers
│   │   ├── scrapers/           # per-source scrapers (NSP, SimplifyJobs)
│   │   ├── scheduler/          # APScheduler job definitions and runner
│   │   └── templates/email/    # HTML email templates
│   ├── data/                   # SQLite DB file + seed data
│   └── requirements.txt
└── frontend/
    └── src/
        ├── pages/               # Login, Register, Dashboard, AdminDashboard
        ├── components/          # cards, filters, layout, common UI
        ├── hooks/                # useSaved, useNotifications
        └── utils/
```

## Getting Started

### Prerequisites
- Python 3.10+ (developed against 3.14)
- Node.js 18+ (developed against 24)

### Clone the repo

```bash
git clone <repository-url>
cd opportunity-matcher
```

### Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

Create `backend/.env` with the following variables:

| Variable | Description |
|---|---|
| `JWT_SECRET` | **Required.** Secret used to sign JWTs; the app refuses to start without it. Use a long random string. |
| `GROQ_API_KEY` | Groq API key for the AI advisor chatbot (`/chat/advisor`). Get one at console.groq.com. Optional — that route returns 503 without it. |
| `DATABASE_URL` | SQLAlchemy database URL. Defaults to `sqlite:///./data/opportunity_matcher.db` if unset. |
| `FRONTEND_URL` | The frontend's origin, used for CORS and links in emails. Defaults to `http://localhost:5173`. |
| `SCHEDULER_ENABLED` | Set to `false` to disable background scraping entirely. Defaults to `true`. |
| `SCRAPER_INTERVAL_HOURS` | Hours between scrape runs. Defaults to `6`. |
| `SCRAPER_INTERVAL_MINUTES` | If set, overrides `SCRAPER_INTERVAL_HOURS` (useful for testing, e.g. `5`). |
| `RUN_SCRAPER_ON_STARTUP` | Set to `true` to run scrapers once immediately on startup. Defaults to `false`. |
| `APP_TIMEZONE` | Timezone for scheduled jobs. Defaults to `Asia/Kolkata`. |
| `MATCH_THRESHOLD` | Minimum match score (0–100) required before a student is notified of a new opportunity. Defaults to `70`. |
| `EMAIL_ENABLED` | Set to `true` to actually send emails via SMTP. Defaults to `false` (logs only). |
| `SMTP_HOST` | SMTP server hostname. Required if `EMAIL_ENABLED=true`. |
| `SMTP_PORT` | SMTP server port. Defaults to `587`. |
| `SMTP_USERNAME` | SMTP auth username. |
| `SMTP_PASSWORD` | SMTP auth password. |
| `SMTP_FROM_EMAIL` | "From" address for outgoing emails. |
| `SMTP_FROM_NAME` | "From" display name. Defaults to `Opportunity Matcher`. |
| `SMTP_USE_TLS` | Whether to use TLS for SMTP. Defaults to `true`. |
| `EMAIL_BATCH_SIZE` | Max emails per notification batch. Defaults to `50`. |
| `EMAIL_DELAY_SECONDS` | Delay between individual emails sent. Defaults to `1`. |
| `EMAIL_MAX_RETRIES` | Retry attempts for a failed email send. Defaults to `3`. |

Run the backend:

```bash
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000`.

### Frontend setup

```bash
cd frontend
npm install
```

Create `frontend/.env` with:

| Variable | Description |
|---|---|
| `VITE_API_URL` | Base URL of the backend API. Defaults to `http://localhost:8000` if unset. |

Run the frontend:

```bash
npm run dev
```

Open `http://localhost:5173`.

## API Overview

All paths are relative to the backend's base URL (e.g. `http://localhost:8000`). "Auth" means a valid `Authorization: Bearer <token>` header is required. "Admin" additionally requires `is_admin=1` on the authenticated user.

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/` | Health check | No |
| GET | `/opportunities` | List active opportunities (cached, `?refresh=true` to force refresh) | No |
| POST | `/register` | Create a new student account, returns a JWT | No (rate-limited) |
| POST | `/login` | Authenticate, returns a JWT | No (rate-limited) |
| GET | `/me` | Get the current authenticated user's profile | Yes |
| POST | `/match` | Compute match scores/eligibility for a given student against all opportunities | No |
| PATCH | `/users/preferences` | Update the current user's notification preferences | Yes |
| PATCH | `/users/profile` | Update the current user's profile (name, branch, year, cgpa, skills) | Yes |
| POST | `/saved` | Save an opportunity for the current user | Yes |
| GET | `/saved` | List the current user's saved opportunities | Yes |
| DELETE | `/saved/{opportunity_id}` | Unsave an opportunity | Yes |
| GET | `/notifications` | List the current user's notifications | Yes |
| PATCH | `/notifications/{id}/read` | Mark one notification as read | Yes |
| PATCH | `/notifications/read-all` | Mark all of the current user's notifications as read | Yes |
| DELETE | `/notifications/{id}` | Delete a notification | Yes |
| POST | `/chat/advisor` | Send a message to the AI career advisor (proxied to Groq) | Yes |
| GET | `/admin/stats` | Full system statistics | Admin |
| GET | `/admin/users` | Paginated user list | Admin |
| GET | `/admin/opportunities` | Paginated, filterable opportunity list | Admin |
| GET | `/admin/scrapers` | Scraper run logs + per-source health | Admin |
| GET | `/admin/notifications` | Notification statistics | Admin |
| GET | `/admin/emails` | Email send statistics + recent failures | Admin |
| GET | `/admin/scraper-status` | Recent scraper logs (legacy) | Admin |
| GET | `/admin/scheduler-status` | Live scheduler job status | Admin |
| POST | `/admin/trigger-scraper` | Manually trigger the scraper pipeline | Admin |
| GET | `/admin/db-stats` | Quick opportunity/user counts (legacy) | Admin |

## Known Limitations

- **SQLite** is used for the database. It's fine for local development and small deployments, but a production deployment expecting concurrent writes or horizontal scaling should migrate to Postgres.
- **No schema migration tool** — `migrations.py` only additively creates tables/columns (`Base.metadata.create_all` + manual column checks); there's no Alembic, so destructive schema changes have no safe upgrade path.
- **Email sending is synchronous** — notification emails are sent in a blocking loop with a `time.sleep()` throttle rather than via a background task queue; this is an intentional simplicity trade-off, not a bug, but won't scale well to a large user base.
- **No refresh tokens** — JWTs are valid for 24 hours with no revocation mechanism; logging out only clears the token client-side.
- **Scrapers are source-specific and fragile** — the National Scholarship Portal and SimplifyJobs scrapers depend on those sites' current HTML/JSON structure and will need maintenance if those sources change.
- **No automated tests** — a `backend/tests` directory exists but is currently empty, and there's no CI pipeline configured in this repository.

## License

No license specified.
