# Score Bot

A Discord bot that tracks daily word-game scores (Wordle, Glyph, Enclose Horse) and posts leaderboards. Includes a web admin panel for managing submissions and toggling games.

## Architecture

| Service | Description |
|---------|-------------|
| `bot` | Discord bot — watches a channel for game results and records scores |
| `web` | FastAPI admin panel at `http://localhost:8000` — secured by Discord OAuth2 |
| `migrate` | One-shot Alembic migration that runs before the other services start |

All three share a SQLite database persisted to `./data/scores.db`.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
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
| `make down` | Stop all services |
| `make logs` | Tail logs from all services |
| `make migrate` | Run database migrations only |
| `make shell` | Open a shell inside the bot container |
| `make clean` | Remove containers, volumes, and the `data/` directory |

## Project Structure

```
score-bot/
├── bot/
│   ├── main.py          # Discord bot entry point
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
