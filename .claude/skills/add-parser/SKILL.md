---
name: add-parser
description: Scaffold a new game parser for score-bot, seed the Game row into the database, and create a migration.
---

Add a new game to score-bot end-to-end: write the parser, create the Alembic migration to seed the Game row, and verify the parser is discovered.

## Steps

### 1. Gather information

Ask the user for the following if not already provided:
- **Game name** — human-readable (e.g. "Wordle", "Mini Crossword")
- **Game ID** — snake_case slug used as the primary key (e.g. `wordle`, `mini_crossword`)
- **Reaction emoji** — the emoji the bot reacts with on a valid submission
- **A sample share message** — the raw text a user would paste into Discord after playing the game
- **Scoring logic** — how to convert the share message into a `base_score` (0–100). Ask the user to describe the rule in plain English (e.g. "fewer guesses = higher score", "faster time = higher score").

### 2. Study the existing parsers

Read two or three existing parsers in `bot/parsers/` (e.g. `wordle.py`, `connections.py`, `mini_crossword.py`) to understand patterns. All parsers must:
- Extend `GameParser` from `bot/parsers/base.py`
- Implement `game_id`, `game_name`, `reaction` properties
- Implement `can_parse(message)` — returns True if the regex matches
- Implement `parse(message, user_id, timestamp)` — returns a `ParseResult` or `None`
- Put the compiled `_PATTERN` regex at module level, not inside methods
- Return `base_score` as a `float` (not int)

### 3. Write the parser

Create `bot/parsers/{game_id}.py` following the patterns above.

Key rules:
- Name the class `{GameName}Parser` (PascalCase)
- `base_score` must be a float in the range `[0.0, 100.0]`; never negative
- `raw_data` dict should capture the raw parsed values (puzzle number, attempts, time, etc.)
- Use `timestamp.date()` for the `date` field in `ParseResult`
- If the game can produce a "fail" result (e.g. X/6 in Wordle), set `base_score = 0.0`

After writing the file, verify the parser is auto-discovered by running:
```bash
python3 -c "from bot.parsers.registry import all_parsers; print([p.game_id for p in all_parsers()])"
```

### 4. Create the Alembic migration

Generate a new migration to seed the Game row:
```bash
alembic revision --autogenerate -m "seed_{game_id}_game"
```

Open the generated file in `alembic/versions/` and replace the auto-generated `upgrade()` body with:
```python
def upgrade() -> None:
    op.execute(
        "INSERT OR IGNORE INTO games (id, name, enabled, created_at) "
        "VALUES ('{game_id}', '{Game Name}', 1, datetime('now'))"
    )

def downgrade() -> None:
    op.execute("DELETE FROM games WHERE id = '{game_id}'")
```

### 5. Write a unit test

Add a test class to `tests/unit/test_parsers.py` following the existing pattern:
- Test `can_parse()` returns True for a valid sample message
- Test `can_parse()` returns False for an unrelated message  
- Test `parse()` returns the expected `base_score` and `raw_data` fields for at least two inputs (e.g. a win and a fail/different score)

Run the tests:
```bash
pytest tests/unit/test_parsers.py -v
```

### 6. Apply the migration and verify

```bash
alembic upgrade head
```

Then confirm the Game row exists:
```bash
python3 -c "
from bot.database import get_engine, Game
from sqlalchemy.orm import Session
db = Session(get_engine('/data/scores.db'))
g = db.get(Game, '{game_id}')
print(g.id, g.name, g.enabled)
db.close()
"
```

If the database isn't accessible locally, note that `make restart` will apply the migration automatically when the container starts.

### 7. Summary

Report back:
- Path to the new parser file
- Path to the new migration file
- Sample parse output for the provided test message (game_id, base_score, raw_data)
- Test results
