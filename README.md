# 🎯 OpportunityMatch

A full-stack app that matches students to internships, hackathons, scholarships and research programs based on their skills and profile.

## Tech Stack
- **Backend:** FastAPI, Python, scikit-learn
- **Frontend:** React + Vite
- **Matching:** TF-IDF Cosine Similarity
- **AI Chatbot:** Groq API (openai/gpt-oss-20b), proxied through the backend — see Recent Changes

## Setup

### 1. Get a free Groq API key
Go to https://console.groq.com → API Keys → Create Key

### 2. Backend setup
```
cd backend
pip install -r requirements.txt
```
Add to backend/.env:
```
GROQ_API_KEY=your_key_here
JWT_SECRET=some-long-random-string
```
`JWT_SECRET` is required — the app now refuses to start without it (see Recent Changes below; there is no insecure default).
The Groq key is used server-side only (`/chat/advisor`) — it does **not** go in the frontend.
Run:
```
uvicorn app.main:app --reload
```

### 3. Frontend setup
```
cd frontend
npm install
```
Add to frontend/.env:
```
VITE_API_URL=http://localhost:8000
```
Run:
```
npm run dev
```

### 4. Open http://localhost:5173

## Features
- Student login & registration (2-step)
- TF-IDF skill matching engine
- Eligibility checker (year, branch, CGPA)
- Match score progress bar on each card
- Requirements brief on every opportunity card
- Edit profile — re-matches instantly
- AI chatbot powered by Groq (ask about opportunities, get cover letters)
- Live opportunities fetched every 10 minutes
- Auto-refresh every 30 seconds

## Recent Changes

> **Note on sourcing:** this project is not a git repository (`git status` /
> `git log` fail — no `.git` directory), so this section was **not** built
> from `git log`/`git diff`. It was built by re-reading the current,
> on-disk content of every file listed below immediately before writing
> this section, cross-referenced against the fixes as they were made and
> live-tested (real HTTP requests against a running backend, real SQLite
> queries against the actual `.db` file) earlier in the same session.
> Line numbers reflect the files' state as of this writing and will drift
> as the code changes further.

### Security Fixes

**JWT_SECRET insecure default.**
`config.py` used to fall back to the hardcoded string `"your-secret-key-change-this"`
if `JWT_SECRET` wasn't set in the environment — anyone reading the source could
forge a valid JWT for any user ID. It now has no fallback and raises
`RuntimeError` at startup if `JWT_SECRET` isn't set.
Files: `backend/app/config.py:16-27`.

**Groq API key moved from the frontend to a backend proxy route.**
The AI chatbot used to call `api.groq.com` directly from the browser with
`VITE_GROQ_API_KEY`, which Vite inlines into the client bundle — visible to
any visitor via devtools or the built JS. A new backend route,
`POST /chat/advisor`, now makes that call server-side using
`config.GROQ_API_KEY`, gated behind a valid JWT so only logged-in users can
spend the app's Groq quota. The frontend no longer references any Groq key
at all.
Files: `backend/app/routes/chat.py` (new, 121 lines), `backend/app/main.py:27,153`
(router registration), `frontend/src/pages/Dashboard.jsx` (removed the
`GROQ_KEY` constant and `buildSystem()`; `send()` in the `Chatbot` component
now calls `POST ${API}/chat/advisor`, lines 461-482).

**CORS origin hardcoded instead of using existing config.**
`main.py` hardcoded `allow_origins=["http://localhost:5173"]` even though
`config.py` already had a configurable `FRONTEND_URL` (used elsewhere for
email links) — any deployment with a different frontend origin would have
had every request blocked by CORS. Now reads `FRONTEND_URL` from config.
Files: `backend/app/main.py:29,92-97`.

**No rate limiting on `/login` or `/register`.**
Both endpoints were open to unlimited brute-force/credential-stuffing
attempts. Added `slowapi`-based rate limiting, 5 requests/minute per IP,
scoped to just these two routes (verified live: 6th rapid request in a
minute returns `429`; an unrelated route like `/opportunities` is
unaffected).
Files: `backend/app/rate_limit.py` (new, shared `Limiter` instance),
`backend/app/main.py:17-20,88-90` (wiring), `backend/app/routes/auth.py:14,28-30,53-55`
(`@limiter.limit("5/minute")` on both routes), `backend/requirements.txt:18-19`
(added `slowapi`).

**No server-side email format or password length validation on `/register`.**
`UserRegister.email` was plain `str` (any string accepted) and there was no
minimum password length enforced server-side (the frontend only showed a
"Min 6 characters" *placeholder hint*, never enforced). Switched `email` to
`pydantic.EmailStr` and added `password: str = Field(min_length=6)` — 6 to
match, not contradict, the frontend's existing hint. Required installing
`email-validator` (pydantic's `EmailStr` dependency). Verified live:
invalid email → `422`; 5-char password → `422`; 6-char password + valid
email → `200` (boundary case). This also surfaced a real frontend bug:
pydantic 422 responses return `detail` as an *array* of error objects, not
a string, and `Register.jsx` was rendering `detail` directly as a React
child — which throws for a non-string array. Fixed by normalizing the
error into a joined string before rendering (see Bug Fixes below).
Files: `backend/app/models/user.py` (`EmailStr` + `Field(min_length=6)`),
`backend/requirements.txt:6` (added `email-validator`).

**Email template placeholder injection.**
`email_templates.py` built each email via a chain of `.replace()` calls,
each re-scanning the *entire accumulated string* — so an untrusted, scraped
opportunity title/description that happened to contain literal text like
`{{APPLY_BUTTON}}` would get silently overwritten by a later `.replace()`
call, corrupting the email's structure. Fixed by substituting all
placeholders in a single `re.sub()` pass over the original template, so a
value that was just inserted is never re-scanned. Verified with both a
normal-data test and a deliberate injection attempt (scraped fields
containing literal `{{...}}` tokens now render inert).
Files: `backend/app/services/email_templates.py:28,37-38,132-156`.

### Bug Fixes

**bcrypt/passlib version incompatibility breaking `/login` and `/register`.**
`passlib==1.7.4`'s bcrypt backend-detection code reads
`bcrypt.__about__.__version__`, which was removed in `bcrypt>=4.0` — the
installed `bcrypt==5.0.0` caused *every* password hash/verify call to fail
with a nonsensical `"password cannot be longer than 72 bytes"` error
(thrown by passlib's own internal self-test, unrelated to actual password
length), returning `500` on both endpoints regardless of credentials.
Fixed by pinning `bcrypt==3.2.2` (the standard fix for this known
incompatibility) and reinstalling. Verified live with real credentials:
register → `200`, login with correct password → `200`, login with wrong
password → `401` (not `500`).
Files: `backend/requirements.txt:8-14`. No application code changed.

**No session restoration on page refresh (`App.jsx`).**
`App.jsx` always started with `student = null` and never checked
`localStorage` for an existing token on mount — despite `JWT_EXPIRE_HOURS = 24`,
any page refresh booted the user back to the login screen. Added a new
`GET /me` backend route and a mount-time check in `App.jsx` that restores
the session from a stored token. This also exposed a related bug: logout
never cleared the stored token (harmless before, since a refresh always
reset state anyway) — now fixed, since a stale token left in `localStorage`
would otherwise silently re-log the user in after "logging out."
Files: `backend/app/routes/auth.py:66-73` (new `GET /me`),
`frontend/src/App.jsx` (rewritten — `restoring` state + restoration
`useEffect`, `handleLogout` now clears the token).

**Profile edits in `Dashboard.jsx` were never persisted.**
The "Save & Re-match" button in the Edit Profile modal only updated local
React state — name/branch/year/CGPA/skills edits were silently lost on
refresh or logout, since no backend route existed for it (only
`PATCH /users/preferences` for notification toggles existed). Added
`PATCH /users/profile` and wired the frontend to call it. Verified live,
including confirming the change landed in the SQLite file on disk, not
just the response body.
Files: `backend/app/routes/users.py:61-104` (new `PATCH /users/profile`),
`frontend/src/pages/Dashboard.jsx:101-127` (`saveProfile`).

**`matcher.py` always said "nd" for ordinal years.**
`check_eligibility()` hardcoded `f"Requires {min_year}nd year or above"`,
producing "Requires 1nd year", "Requires 3nd year", etc. for every value.
Added a small `_ordinal()` helper and use it instead; verified correct for
1st/2nd/3rd/4th plus edge cases (11th–13th, 21st–23rd).
Files: `backend/app/services/matcher.py:4-10,44`.

**`matcher.py` bare `except:`.**
`compute_match_score()` caught every exception (including e.g.
`KeyboardInterrupt`) and silently returned `0`, masking unrelated bugs as
"no match." Narrowed to `except ValueError:` (the actual failure mode,
confirmed directly — `TfidfVectorizer` raises `ValueError: empty
vocabulary` when both documents are empty). Verified: the real case (empty
student skills) still returns `0`; an injected `TypeError` now correctly
propagates instead of being swallowed.
Files: `backend/app/services/matcher.py:29`.

**Duplicate `CACHE_MINUTES` constant.**
Both `config.py` and `main.py` independently defined `CACHE_MINUTES = 10` —
editing one had no effect on the other. `main.py` now imports it from
`config.py`.
Files: `backend/app/main.py:29` (removed local constant, added to the
existing `config` import).

**Dead sort options in `FilterPanel.jsx` ("Newest", "Salary").**
Both silently fell back to "Highest Match" — Dashboard's sort function
never implemented them. "Newest" was genuinely implementable (`created_at`
already existed on `OpportunityTable`, just wasn't exposed via `to_dict()`)
and is now wired up. "Salary" was removed instead of faked — `stipend` is
free-text (`"₹50,000/mo"`, `"Unpaid"`, `None`, arbitrary scraped strings)
with no structured numeric value, so sorting by it would mean guessing at
parsing arbitrary formats, which conflicts with this codebase's own
explicit "never fabricate/guess" convention (see the scrapers and
`opportunity_validator.py`). Verified against live data with the exact
frontend comparator.
Files: `backend/app/database/models.py:171` (`created_at` added to
`to_dict()`), `frontend/src/components/filters/FilterPanel.jsx:5` ("Salary"
removed), `frontend/src/pages/Dashboard.jsx:97` ("Newest" implemented).

**Deadline-null sort bug (found while fixing the item above).**
"Deadline Soon" used `new Date(a.opportunity.deadline)` directly —
`new Date(null)` evaluates to the Unix epoch (1970), so any opportunity
with no deadline sorted as "soonest," burying real deadlines. This was a
real, high-impact bug in practice: of the 222 opportunities in the live DB,
205 (all SimplifyJobs listings, which don't provide a deadline) had
`deadline: null`. Fixed to push undated opportunities to the end instead.
Verified against live data: all 17 dated opportunities now sort first in
correct ascending order; all 205 undated ones are pushed to the end.
Files: `frontend/src/pages/Dashboard.jsx:86-96`.

**Deduplicator URL-normalization bug.**
`find_by_url()` normalized only the *incoming* URL and compared it against
the *raw, never-normalized* stored `link` column, so two scrapes of the
same job differing only by a tracking parameter (e.g. `?utm_source=a` vs
`?utm_source=b`) never matched — every such duplicate silently fell through
to the content-hash fallback, defeating the documented "primary: URL
match" design. Fixed by adding a `normalized_link` column (used only for
dedup matching — kept separate from `link` so the real Apply-button URL is
never altered) populated at insert time and backfilled for existing rows;
`find_by_url` now compares both sides after the same normalization. Also
corrected a misleading docstring: the normalization function actually
strips *all* query parameters, not just tracking-only ones as previously
claimed. Verified against the live 222-row database: fresh-startup
migration log showed `Backfilled normalized_link for 222/222 opportunities`;
a full `save_opportunity()` pipeline test with a real URL + added tracking
params correctly returned `"duplicate"` with the same `opportunity_id`
(only 1 row persisted, not 2).
Files: `backend/app/database/models.py:118-123,148` (new column + index),
`backend/app/services/deduplicator.py:33-59,96-118` (`normalize_url` made
public, `find_by_url` fixed), `backend/app/services/opportunity_repository.py:24,44`
(computed on insert), `backend/app/database/migrations.py:16,61-63,82-113,199`
(column migration + `_backfill_normalized_links()`).

**`connection.py` DATABASE_URL duplication** (found while verifying the
SQLite setup, same class of bug as the `CACHE_MINUTES` duplication above).
`connection.py` read `DATABASE_URL` from the environment independently of
`config.py`, via its own `os.getenv` call with a matching default — harmless
today since both defaults agreed, but a latent risk if they ever drifted.
Now imports `DATABASE_URL` from `config.py`.
Files: `backend/app/database/connection.py:1-10`.

**`Sidebar.jsx` mobile/desktop visibility didn't react to window resizing.**
`window.innerWidth < 1024` was read once during render with no `resize`
listener, so the sidebar's visibility class was stale until some unrelated
re-render happened to fire. Fixed by dropping the JS check entirely — the
component's own CSS media query (`@media (max-width: 1023px)`) already
scoped the `.sidebar-hidden` class's effect to the same breakpoint, making
the JS check redundant with it. Confirmed by walking through every
desktop/mobile × open/closed combination: the CSS-only version produces
identical results in every case, since the JS check never added any
behavior the CSS wasn't already providing. Also removed an unrelated dead
`import { useState }` in the same file (this component has no `useState`
calls at all), caught by lint while verifying.
Files: `frontend/src/components/layout/Sidebar.jsx:1,32`.

**`Register.jsx` would crash on a validation error response.**
Found while verifying the new `EmailStr`/password-length validation above.
FastAPI/pydantic 422 responses return `detail` as an array of error
objects, not a string; `Register.jsx` rendered `e.response.data.detail`
directly as a React child, which throws when it's a non-string array.
Fixed by normalizing the error into a joined string before storing it in
state. Verified against a real 422 response carrying two simultaneous
errors (bad email + short password) — now renders as one readable string
instead of crashing.
Files: `frontend/src/pages/Register.jsx:31-38`.

**`notification_service.py` scalability: full `users` table re-scanned once per opportunity.**
`match_new_opportunity()` ran `db.query(UserTable).all()` fresh for every
single newly-inserted opportunity — since it fired from inside
`save_opportunity()`'s per-record insert path, a single scrape run
inserting up to ~500 opportunities meant up to 500 redundant full-table
scans of `users` per run, getting more expensive as the user base grows.
Restructured so the notification pass runs ONCE per scrape *batch*
instead of once per opportunity: extracted the per-opportunity logic into
`_match_one_opportunity(db, students, opportunity, threshold)` (takes an
already-loaded `students` list instead of querying it itself), added
`match_new_opportunities(opportunities)` as the new preferred batched
entry point (loads `students` once, evaluates every opportunity in the
batch against it), and moved the trigger point from
`opportunity_repository.save_opportunity()` (per-record) to
`save_opportunities()` (once, after the whole batch is inserted). The
original single-opportunity `match_new_opportunity()` is kept as a thin
wrapper around the batched form, for any caller that only has one
opportunity to evaluate.

This surfaced a second, related issue while verifying the fix: `SessionLocal`
doesn't set `expire_on_commit` (SQLAlchemy defaults it to `True`), so every
`db.commit()` inside the loop (once per notification row, once per email-
history row) was silently expiring every cached `user` object, forcing a
fresh single-row `SELECT ... WHERE id = ?` on the next attribute access —
undermining the whole point of loading `students` once. Fixed by opening
the batched function's session with `SessionLocal(expire_on_commit=False)`,
scoped to just that one session (the app-wide `SessionLocal` default is
untouched) — safe here since this code only reads `user` rows and the rows
it does write use client-generated UUIDs, not server-generated values that
would need a post-commit refresh.

Verified directly by counting actual SQL statements via a SQLAlchemy
`before_cursor_execute` hook against the real dev database: a 5-opportunity
batch dropped from 29 total `SELECT ... FROM users` statements (1 real
`.all()` scan + 28 commit-triggered single-row refreshes) down to exactly
1; a 20-opportunity batch also stayed at exactly 1, confirming the fix is
O(1) in batch size, not O(N). Also verified: notification counts still
correct (5 notifications for 5 opportunities, 20 for 20), the kept
single-opportunity `match_new_opportunity()` API still works and notifies
the right user, and an ineligible user (wrong branch/skills) is still
correctly *not* notified — the refactor changed only where the `users`
query happens, not the matching logic itself. Deliberately left unchanged:
the synchronous, `time.sleep()`-throttled email-sending loop within each
opportunity's evaluation — that's an existing, explicitly documented
design decision in this codebase (see the module's own comments), not a
bug, and addressing it would mean introducing background task
infrastructure this project has consistently avoided elsewhere.
Files: `backend/app/services/notification_service.py` (extracted
`_match_one_opportunity`, new `match_new_opportunities`, `expire_on_commit=False`),
`backend/app/services/opportunity_repository.py` (`save_opportunity` no
longer triggers notifications itself and now returns the inserted
opportunity dict; `save_opportunities` collects inserted opportunities and
calls `match_new_opportunities` once after the batch completes).

### Database

SQLite was already fully configured before this session — no wiring was
needed, only verification:
- `backend/app/database/connection.py` — SQLAlchemy engine, `SessionLocal`
  session factory, `Base`, `get_db()` FastAPI dependency.
- `backend/app/database/models.py` — 6 ORM tables (`UserTable`,
  `OpportunityTable`, `SavedOpportunityTable`, `NotificationTable`,
  `EmailHistoryTable`, `ScraperLogTable`).
- `backend/app/database/migrations.py` — `run_migrations()` (called from
  `main.py`'s FastAPI `lifespan` on every startup) creates tables
  (`Base.metadata.create_all`, idempotent), additively adds any missing
  columns, and seeds `data/sample_opportunities.json` only if the table is
  empty. No Alembic — additive-only schema changes have been sufficient so
  far.
- `backend/.env`: `DATABASE_URL=sqlite:///./data/opportunity_matcher.db`,
  read by `config.py` via `os.getenv` (not hardcoded).
- The one database-related bug found and fixed this session: the
  `connection.py` `DATABASE_URL` duplication (see Bug Fixes above), and the
  `normalized_link` schema addition + migration/backfill (see the
  deduplicator fix above).
- Verified end-to-end live against the real file (`backend/data/opportunity_matcher.db`,
  222 real opportunities from prior scraper runs): register → login →
  `GET /me` → `GET /opportunities` → `POST /match` → `GET /saved`, all
  hitting the real database, with several writes (registration,
  profile updates) confirmed directly via `sqlite3` queries against the
  file, not just trusting API responses.

### Known Issues / Not Yet Fixed

Everything from the original full-codebase review has now been addressed.

Deliberately left as-is, not a bug: the synchronous, `time.sleep()`-throttled
email-sending loop inside `notification_service.py`'s per-opportunity
evaluation (see the scalability fix above) — an explicit, documented design
decision in this codebase, not something flagged as broken.

Resolved as a side effect of a fix above, not separately: `config.GROQ_API_KEY`
was previously unused/dead code (the frontend called Groq directly instead)
— it's now genuinely used by `backend/app/routes/chat.py`.
