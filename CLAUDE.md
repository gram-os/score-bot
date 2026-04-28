# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Setup and run:**
```bash
make setup    # copy .env.example → .env, generate SECRET_KEY
make up       # build images, run migrations, start bot + web
make restart  # rebuild images and restart (required after any code change)
make down     # stop all services
make logs     # tail logs
make migrate  # run migrations only
make clean    # remove containers, volumes, and data/
```

> **Important:** Code is baked into the Docker image at build time — `docker restart` runs stale code. Always use `make restart` (not `docker restart`) after editing source files.

**Testing:**
```bash
pip install -r requirements-dev.txt
pytest                          # all tests
pytest -m unit                  # unit tests only (no DB)
pytest -m integration           # integration tests (require DB)
pytest tests/unit/test_parsers.py::TestWordleParser  # single test class
```

**Linting / formatting:**
```bash
ruff format .   # format (replaces black)
ruff check .    # lint (replaces flake8)
```

**Migrations:**
```bash
alembic upgrade head            # apply migrations
alembic revision --autogenerate -m "description"  # generate new migration
```

## Architecture

Three services share a single SQLite database at `./data/scores.db`:

- **`bot/`** — Discord bot (`discord.py`). `ScoreBot` in `main.py` listens to one channel (`DISCORD_CHANNEL_ID`), runs each message through `ParserRegistry`, and records scores. Exposes `/leaderboard` and `/games` slash commands.
- **`web/`** — FastAPI admin panel. `auth.py` handles Discord OAuth2 login and contains all admin routes (`/admin/submissions`, `/admin/games`, `/admin/leaderboard`). Protected by `require_admin` which checks session against `ADMIN_DISCORD_IDS`.
- **`migrate`** — Runs Alembic migrations once at startup before other services.

### Parser system

Each game has a parser in `bot/parsers/` that extends `GameParser` (ABC in `base.py`). Parsers implement:
- `can_parse(message)` — regex match to detect the game
- `parse(message, user_id, timestamp) → ParseResult | None` — extract `base_score` and `raw_data`

`ParserRegistry` (`bot/parsers/registry.py`) auto-discovers all `GameParser` subclasses. Adding a new game requires only a new file in `bot/parsers/` — no registry changes needed.

### Scoring

`total_score = base_score + speed_bonus`. Speed bonus is awarded per-game per-day: 1st submission +15, 2nd +10, 3rd +5. This is recalculated across all submissions for that game+date on every insert or delete (`assign_submission_rank` in `scoring.py`).

### Database

`Submission` has a unique constraint on `(user_id, game_id, date)` — one submission per player per game per day. `record_submission` in `database.py` handles the flush+rank-reassignment pattern; always call through this function, not by directly adding `Submission` objects.

### Auth

Authentication is handled by Cloudflare Access (email OTP) at the edge. Every request to the admin panel must carry a valid `Cf-Access-Jwt-Assertion` header; `web/deps.py` verifies it via RS256 against the team's JWKS endpoint before any route handler runs.

Admin access is controlled by `ADMIN_EMAILS` and `HOMUNCULUS_VIEWER_EMAILS` env vars (comma-separated emails). There is no role table. Session cookie (signed with `SECRET_KEY`) stores the `role` and `email` for template rendering and audit logs after a successful JWT check.

## Git Environment Notes
- This repo may not have `origin/HEAD` set. When diffing against the default branch, use `origin/main` explicitly rather than `origin/HEAD`.
- If a slash command fails at a git step, surface the error to the user immediately rather than silently exiting.

## Coding Style

- **Atomic Functions:** Prefer many small, single-purpose functions (10-20 lines) over large logic blocks.
- **DRY (Don't Repeat Yourself):** Actively look for duplicated logic across services (bot/web) and move shared logic to a common utility or service layer.
- **Maintain Contracts:** When refactoring, ensure existing function signatures and API endpoints remain stable. If a breaking change is necessary, document it clearly before proceeding.
- **No Inline Imports:** All imports must be at the top of the file. Do not use imports inside functions or classes to solve circular dependencies; refactor the architecture instead.
- **Type Hinting:** Use strict Python type hints for all new function signatures and class attributes.
- **Async Efficiency:** Both bot and web services are async. Avoid blocking I/O; use `await` where possible or `run_in_executor` for CPU-bound tasks.
