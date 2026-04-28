"""
One-off backfill for two scoring rule changes:
  1. Quordle base_score: new formula (9 - avg_attempts) / 5 * 100; 0 if failed
  2. Speed bonus: no longer awarded when base_score == 0 (any game)

Run from project root:
  DATABASE_PATH=./data/scores.db python scripts/backfill_scoring.py
  DATABASE_PATH=./data/scores.db python scripts/backfill_scoring.py --dry-run
"""

import argparse
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.db.models import Game, Submission, get_engine
from bot.db.submissions import recalculate_game_ranks


def new_quordle_base_score(raw_data: dict) -> float:
    if raw_data.get("failed"):
        return 0.0
    attempts = raw_data.get("attempts", [])
    if len(attempts) != 4:
        return 0.0
    avg = sum(attempts) / 4
    return min(100.0, max(0.0, (9.0 - avg) / 5.0 * 100))


def backfill_quordle_scores(session: Session, dry_run: bool) -> int:
    submissions = session.scalars(select(Submission).where(Submission.game_id == "quordle")).all()

    changed = 0
    for sub in submissions:
        new_score = new_quordle_base_score(sub.raw_data)
        if new_score != sub.base_score:
            print(
                f"  quordle #{sub.raw_data.get('puzzle_number')} "
                f"user={sub.user_id} date={sub.date}: "
                f"base_score {sub.base_score} → {new_score}"
            )
            if not dry_run:
                sub.base_score = new_score
            changed += 1

    return changed


def backfill_all_ranks(session: Session, dry_run: bool) -> None:
    game_ids = session.scalars(select(Game.id)).all()
    for game_id in game_ids:
        if not dry_run:
            recalculate_game_ranks(session, game_id)
        print(f"  recalculated ranks for {game_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="preview changes without writing")
    args = parser.parse_args()

    db_path = os.environ.get("DATABASE_PATH", "./data/scores.db")
    engine = get_engine(db_path)

    with Session(engine) as session:
        print(f"{'[DRY RUN] ' if args.dry_run else ''}Backfilling Quordle base scores...")
        changed = backfill_quordle_scores(session, args.dry_run)
        print(f"  {changed} Quordle submissions updated")

        print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Recalculating ranks and speed bonuses for all games...")
        backfill_all_ranks(session, args.dry_run)

        if not args.dry_run:
            session.commit()
            print("\nDone — changes committed.")
        else:
            print("\nDry run complete — no changes written.")


if __name__ == "__main__":
    main()
