# Score Bot

A Discord bot that tracks daily word-game scores and posts leaderboards. Includes a web admin panel for managing submissions and toggling games.

## Supported Games

| Game | Parser ID |
|------|-----------|
| Wordle | `wordle` |
| Glyph | `glyph` |
| Enclose Horse | `enclose_horse` |
| Mini Crossword | `mini_crossword` |
| Quordle | `quordle` |
| Connections | `connections` |

Adding a new game requires only a new parser file in `bot/parsers/` — no registry changes needed.

## Architecture

| Service | Description |
|---------|-------------|
| `bot` | Discord bot — watches a channel for game results and records scores |
| `web` | FastAPI admin panel at `http://localhost:8000` — secured by Discord OAuth2 |
| `migrate` | One-shot Alembic migration that runs before the other services start |

All three share a SQLite database persisted to `./data/scores.db`.

## Bot Commands

| Command | Description |
|---------|-------------|
| `/leaderboard [game] [period]` | Show the leaderboard, filtered by game and time period (daily / weekly / monthly / all-time) |
| `/games` | List currently enabled games |
| `/suggest <game_name> [description]` | Suggest a game to be added; queues it for the next daily poll |
| `/vs <opponent> [game]` | Head-to-head comparison between you and another player |
| `/best <game> [user]` | Show personal bests, average score, and current streak for a game |
| `/remind [threshold]` | Opt in or out of streak reminder DMs (threshold = minimum streak length, 0 = opt out) |
| `/help` | Show a summary of what the bot does and all available commands (visible only to you) |

## Automated Daily Tasks

The bot runs three scheduled jobs after startup:

| Job | Default time (UTC) | Env var | Description |
|-----|--------------------|---------|-------------|
| Suggestion poll | 09:00 | `POLL_HOUR` | Posts a Discord native poll from queued suggestions; resolves the previous poll, announces the winner, and DMs admins if a game passes |
| Daily digest | 09:00 | `DIGEST_TIME` | Posts an embed summarising yesterday's winner and top streak per game |
| Streak reminders | 20:00 | `REMINDER_TIME` | DMs users who are on a qualifying streak but haven't submitted today |

## Admin Panel

Accessible at `http://localhost:8000` after Discord OAuth2 login. Only users listed in `ADMIN_DISCORD_IDS` can access admin routes.

| Route | Description |
|-------|-------------|
| `/admin/submissions` | Browse submissions, delete entries, and manually add new ones |
| `/admin/games` | Enable or disable individual games |
| `/admin/leaderboard` | View the leaderboard |
| `/admin/stats` | Submission timeline and activity stats |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)
- A Discord application with a bot token and OAuth2 credentials (see below)

## Environment Variables

Copy `.env.example` to `.env` (or run `make setup` to do it automatically):

```
make setup
```

Then fill in the values:

| Variable | Description | Where to get it |
|----------|-------------|-----------------|
| `DISCORD_TOKEN` | Bot token | [Discord Developer Portal](https://discord.com/developers/applications) → your app → **Bot** → Token |
| `DISCORD_CHANNEL_ID` | Channel ID the bot monitors | Right-click the channel in Discord → **Copy Channel ID** (requires Developer Mode) |
| `DISCORD_CLIENT_ID` | OAuth2 client ID | Developer Portal → your app → **OAuth2** → Client ID |
| `DISCORD_CLIENT_SECRET` | OAuth2 client secret | Developer Portal → your app → **OAuth2** → Client Secret |
| `DISCORD_REDIRECT_URI` | OAuth2 redirect URI | Must match a URI added under **OAuth2 → Redirects**; default `http://localhost:8000/auth/callback` |
| `ADMIN_DISCORD_IDS` | Comma-separated Discord user IDs allowed to access the admin panel | Right-click your profile in Discord → **Copy User ID** (requires Developer Mode) |
| `SECRET_KEY` | Session cookie signing key | Generated automatically by `make setup` (`openssl rand -hex 32`) |
| `DATABASE_PATH` | Path to the SQLite file inside the container | Defaults to `/data/scores.db` — no change needed |
| `POLL_HOUR` | Hour (UTC) to post the daily suggestion poll | Integer, default `9` |
| `DIGEST_TIME` | Time (UTC) to post the daily digest (`HH:MM`) | Default `09:00` |
| `REMINDER_TIME` | Time (UTC) to send streak reminder DMs (`HH:MM`) | Default `20:00` |

### Enabling Developer Mode in Discord

Settings → Advanced → **Developer Mode** — enables right-click copy IDs.

### Discord App Setup Checklist

1. Create an application at [discord.com/developers/applications](https://discord.com/developers/applications).
2. Under **Bot**, create a bot, copy the token, and enable the **Message Content Intent**.
3. Under **OAuth2 → Redirects**, add `http://localhost:8000/auth/callback`.
4. Invite the bot to your server using the OAuth2 URL generator with scopes `bot` and `applications.commands` and permissions for **Read Messages**, **Add Reactions**.

## Running Locally

```bash
make setup    # copy .env.example → .env and generate SECRET_KEY
# edit .env and fill in your tokens
make up       # build images, run migrations, start bot + web
```

The admin panel is available at [http://localhost:8000](http://localhost:8000).

## Make Targets

| Target | Description |
|--------|-------------|
| `make setup` | Copy `.env.example` → `.env`, generate `SECRET_KEY` |
| `make build` | Build Docker images |
| `make up` | Start all services in the background |
| `make restart` | Rebuild images and restart all services (use after code changes) |
| `make down` | Stop all services |
| `make logs` | Tail logs from all services |
| `make migrate` | Run database migrations only |
| `make shell` | Open a shell inside the bot container |
| `make clean` | Remove containers, volumes, and the `data/` directory |

## Project Structure

```
score-bot/
├── bot/
│   ├── main.py          # Discord bot entry point and slash commands
│   ├── database.py      # SQLAlchemy models and queries
│   ├── scoring.py       # Score calculation logic
│   └── parsers/         # One parser per supported game
├── web/
│   ├── main.py          # FastAPI app
│   ├── auth.py          # Discord OAuth2 + admin routes
│   ├── templates/       # Jinja2 HTML templates
│   └── static/          # CSS / JS assets
├── alembic/             # Database migrations
├── data/                # SQLite database (created at runtime, git-ignored)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── Makefile
```
