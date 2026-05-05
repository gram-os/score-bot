from datetime import date, datetime, timezone

from sqlalchemy import select

from bot.database import (
    Submission,
    add_submission_manual,
    preview_recalculate_game_ranks,
)


TODAY = date(2024, 1, 15)


def _add(session, user_id: str, username: str, base_score: float, hour: int, game_id: str = "wordle"):
    return add_submission_manual(
        session,
        user_id=user_id,
        username=username,
        game_id=game_id,
        submission_date=TODAY,
        base_score=base_score,
        raw_data={},
        submitted_at=datetime(2024, 1, 15, hour, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None),
    )


class TestPreviewRecalculate:
    def test_no_changes_when_already_in_sync(self, session, wordle_game):
        _add(session, "u1", "Alice", 80.0, hour=8)
        _add(session, "u2", "Bob", 70.0, hour=9)

        diffs = preview_recalculate_game_ranks(session, "wordle")
        assert diffs == []

    def test_detects_rank_swap_after_manual_corruption(self, session, wordle_game):
        s1 = _add(session, "u1", "Alice", 80.0, hour=8)
        s2 = _add(session, "u2", "Bob", 70.0, hour=9)

        # Corrupt the DB: swap ranks/totals to simulate stale state.
        s1.submission_rank = 2
        s1.speed_bonus = 10
        s1.total_score = 90.0
        s2.submission_rank = 1
        s2.speed_bonus = 15
        s2.total_score = 85.0
        session.flush()

        diffs = preview_recalculate_game_ranks(session, "wordle")
        assert len(diffs) == 2
        by_user = {d.username: d for d in diffs}
        assert by_user["Alice"].current_rank == 2
        assert by_user["Alice"].new_rank == 1
        assert by_user["Alice"].current_total == 90.0
        assert by_user["Alice"].new_total == 95.0
        assert by_user["Bob"].current_rank == 1
        assert by_user["Bob"].new_rank == 2
        assert by_user["Bob"].new_total == 80.0

    def test_preview_does_not_mutate_db(self, session, wordle_game):
        s1 = _add(session, "u1", "Alice", 80.0, hour=8)
        s2 = _add(session, "u2", "Bob", 70.0, hour=9)

        # Corrupt to make sure preview would *want* to change something.
        s1.submission_rank = 2
        s1.speed_bonus = 10
        s1.total_score = 90.0
        s2.submission_rank = 1
        s2.speed_bonus = 15
        s2.total_score = 85.0
        session.flush()

        before = {
            row.id: (row.submission_rank, row.speed_bonus, row.total_score)
            for row in session.scalars(select(Submission)).all()
        }
        preview_recalculate_game_ranks(session, "wordle")
        session.expire_all()
        after = {
            row.id: (row.submission_rank, row.speed_bonus, row.total_score)
            for row in session.scalars(select(Submission)).all()
        }
        assert before == after

    def test_respects_date_range(self, session, wordle_game):
        sub = add_submission_manual(
            session,
            user_id="u1",
            username="Alice",
            game_id="wordle",
            submission_date=date(2024, 1, 10),
            base_score=80.0,
            raw_data={},
            submitted_at=datetime(2024, 1, 10, 8, 0, 0),
        )
        sub.submission_rank = 9
        sub.total_score = 999.0
        session.flush()

        diffs_in = preview_recalculate_game_ranks(
            session, "wordle", start_date=date(2024, 1, 10), end_date=date(2024, 1, 10)
        )
        assert len(diffs_in) == 1

        diffs_out = preview_recalculate_game_ranks(
            session, "wordle", start_date=date(2024, 1, 11), end_date=date(2024, 1, 20)
        )
        assert diffs_out == []

    def test_zero_score_submission_keeps_rank_zero(self, session, wordle_game):
        _add(session, "u1", "Alice", 0.0, hour=8)
        diffs = preview_recalculate_game_ranks(session, "wordle")
        assert diffs == []
