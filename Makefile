.PHONY: help setup build up down logs migrate shell clean check test test-unit test-integration

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  setup    Copy .env.example to .env and generate a SECRET_KEY"
	@echo "  build    Build Docker images"
	@echo "  up       Start all services (migrate + bot + web)"
	@echo "  restart  Rebuild images and restart all services (use after code changes)"
	@echo "  down     Stop all services"
	@echo "  logs     Tail logs from all services"
	@echo "  migrate  Run database migrations only"
	@echo "  shell    Open a shell inside the bot container"
	@echo "  clean    Remove containers, volumes, and the data directory"
	@echo "  check    Run black, flake8, and pytest (run before committing)"

setup:
	@if [ -f .env ]; then \
		echo ".env already exists — skipping copy"; \
	else \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	fi
	@if grep -q '^SECRET_KEY=$$' .env; then \
		SECRET=$$(openssl rand -hex 32); \
		sed -i.bak "s|^SECRET_KEY=$$|SECRET_KEY=$$SECRET|" .env && rm -f .env.bak; \
		echo "Generated SECRET_KEY"; \
	else \
		echo "SECRET_KEY already set — skipping"; \
	fi
	@echo ""
	@echo "Next: fill in DISCORD_TOKEN, DISCORD_CHANNEL_ID, DISCORD_CLIENT_ID,"
	@echo "      DISCORD_CLIENT_SECRET, and ADMIN_DISCORD_IDS in .env"

build:
	docker compose build

up:
	mkdir -p data
	docker compose up -d

restart:
	docker compose build
	mkdir -p data
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	mkdir -p data
	docker compose run --rm migrate

shell:
	docker compose run --rm bot /bin/bash

clean:
	docker compose down -v
	rm -rf data

check:
	black .
	flake8 .
	pytest

test: test-unit test-integration

test-unit:
	.venv/bin/pytest tests/unit -v -m unit

test-integration:
	.venv/bin/pytest tests/integration -v -m integration
