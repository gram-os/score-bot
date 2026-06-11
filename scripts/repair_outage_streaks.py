"""
Repair streaks broken by a known bot outage window, and award the
"Talking to the Void" achievement to players who were active during it.

Run AFTER the bot has restarted and startup_backfill has processed all missed
Discord messages. This script handles users who missed 2+ days during the
outage — something the normal freeze system can't cover.

What it does:
  - For each UserStreak whose last_submission_date falls within the outage
    window (inclusive of the day before), check if the streak is now stale.
  - If stale, bridge the gap by advancing last_submission_date to outage_end.
  - Awards "talking_to_the_void" to any user who had submissions replayed from
    the outage window (they kept posting while the bot was deaf).
  - Users who submitted through the outage via backfill have their streaks
    untouched — their last_submission_date is already up to date.

Usage:
  DATABASE_PATH=./data/scores.db python scripts/repair_outage_streaks.py \
      --outage-start 2026-06-05 --outage-end 2026-06-11
  DATABASE_PATH=./data/scores.db python scripts/repair_outage_streaks.py \
      --outage-start 2026-06-05 --outage-end 2026-06-11 --dry-run
"""

import argparse
import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.achievements import ACHIEVEMENTS
from bot.db.models import Submission, User, UserAchievement, UserStreak, get_engine


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def repair_outage_streaks(
    session: Session,
    outage_start: date,
    outage_end: date,
    dry_run: bool,
) -> int:
    # A streak is "caught" by the outage if the last submission was in the window
    # [outage_start - 1, outage_end]. The -1 handles users who last submitted the
    # day before the outage began and never got a chance to post during it.
    window_start = outage_start - timedelta(days=1)

    rows = session.scalars(select(UserStreak).where(UserStreak.last_submission_date.isnot(None))).all()

    repaired = 0
    for streak in rows:
        last = streak.last_submission_date
        if last is None:
            continue

        # Already updated past the outage — backfill did its job.
        if last > outage_end:
            continue

        # Not in the window we care about.
        if last < window_start:
            continue

        # Streak is stale: gap to outage_end is > 1, so it reads as 0 right now.
        days_since = (outage_end - last).days
        if days_since <= 1:
            continue

        user = session.get(User, streak.user_id)
        username = user.username if user else streak.user_id

        print(
            f"  {'[DRY RUN] ' if dry_run else ''}repair "
            f"user={username} game={streak.game_id} "
            f"streak={streak.current_streak} "
            f"last={last} → {outage_end}"
        )

        if not dry_run:
            streak.last_submission_date = outage_end

        repaired += 1

    return repaired


def award_witness_achievement(
    session: Session,
    outage_end: date,
    dry_run: bool,
) -> int:
    slug = "outage_witness"
    if slug not in ACHIEVEMENTS:
        print(f"  WARNING: achievement '{slug}' not found in ACHIEVEMENTS — skipping")
        return 0

    already_earned = set(
        session.scalars(select(UserAchievement.user_id).where(UserAchievement.achievement_slug == slug)).all()
    )

    # Anyone with at least one submission on or before the outage end — they existed.
    active_user_ids = session.scalars(select(Submission.user_id).where(Submission.date <= outage_end).distinct()).all()

    awarded = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for user_id in active_user_ids:
        if user_id in already_earned:
            continue

        user = session.get(User, user_id)
        username = user.username if user else user_id

        print(f"  {'[DRY RUN] ' if dry_run else ''}award outage_witness → {username}")

        if not dry_run:
            session.add(
                UserAchievement(
                    user_id=user_id,
                    achievement_slug=slug,
                    display_name=ACHIEVEMENTS[slug].name,
                    earned_at=now,
                )
            )

        awarded += 1

    return awarded


def award_outage_achievement(
    session: Session,
    outage_start: date,
    outage_end: date,
    dry_run: bool,
) -> int:
    slug = "talking_to_the_void"
    if slug not in ACHIEVEMENTS:
        print(f"  WARNING: achievement '{slug}' not found in ACHIEVEMENTS — skipping")
        return 0

    already_earned = set(
        session.scalars(select(UserAchievement.user_id).where(UserAchievement.achievement_slug == slug)).all()
    )

    # Find all distinct users who have at least one submission during the outage window.
    # These are the brave souls who kept posting while the bot wasn't listening.
    active_user_ids = session.scalars(
        select(Submission.user_id).where(Submission.date >= outage_start, Submission.date <= outage_end).distinct()
    ).all()

    awarded = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for user_id in active_user_ids:
        if user_id in already_earned:
            continue

        user = session.get(User, user_id)
        username = user.username if user else user_id

        print(f"  {'[DRY RUN] ' if dry_run else ''}award talking_to_the_void → {username}")

        if not dry_run:
            session.add(
                UserAchievement(
                    user_id=user_id,
                    achievement_slug=slug,
                    display_name=ACHIEVEMENTS[slug].name,
                    earned_at=now,
                )
            )

        awarded += 1

    return awarded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--outage-start",
        required=True,
        type=parse_date,
        help="First day of the outage (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--outage-end",
        required=True,
        type=parse_date,
        help="Last day of the outage (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the database",
    )
    args = parser.parse_args()

    if args.outage_end < args.outage_start:
        parser.error("--outage-end must be >= --outage-start")

    db_path = os.environ.get("DATABASE_PATH", "./data/scores.db")
    engine = get_engine(db_path)

    label = "[DRY RUN] " if args.dry_run else ""
    print(f"{label}Repairing streaks for outage {args.outage_start} → {args.outage_end}")

    with Session(engine) as session:
        repaired = repair_outage_streaks(session, args.outage_start, args.outage_end, args.dry_run)

        print(f"\n{label}Awarding 'Talking to the Void' achievement...")
        awarded_void = award_outage_achievement(session, args.outage_start, args.outage_end, args.dry_run)

        print(f"\n{label}Awarding 'You Were There' achievement...")
        awarded_witness = award_witness_achievement(session, args.outage_end, args.dry_run)

        total_awarded = awarded_void + awarded_witness

        if not args.dry_run:
            session.commit()
            print(f"\nDone — {repaired} streak(s) repaired, {total_awarded} achievement(s) awarded.")
        else:
            print(
                f"\nDry run complete — {repaired} streak(s) would be repaired, "
                f"{total_awarded} achievement(s) would be awarded."
            )


if __name__ == "__main__":
    main()
