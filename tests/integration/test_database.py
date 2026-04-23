from datetime import date, datetime, timedelta, timezone

from bot.database import (
    Game,
    Submission,
    add_submission_manual,
    delete_submission,
    get_all_streaks,
    get_leaderboard,
    get_streak,
    is_duplicate,
    record_submission,
    update_streak_on_submission,
    upsert_user,
)
from bot.parsers.base import ParseResult

TODAY = date(2024, 1, 15)


def _make_result(
    user_id: str, base_score: float = 75.0, game_id: str = "wordle"
) -> ParseResult:
    return ParseResult(
        game_id=game_id,
        user_id=user_id,
        date=TODAY,
        base_score=base_score,
        raw_data={"attempts": 3},
    )


# ---------------------------------------------------------------------------
# record_submission
# ---------------------------------------------------------------------------


class TestRecordSubmission:
    def test_creates_row_in_db(self, session, wordle_game):
        result = record_submission(session, _make_result("user1"), username="Alice")
        assert result is not None
        assert result.id is not None
        assert result.user_id == "user1"
        assert result.username == "Alice"
        assert result.base_score == 75.0

    def test_first_submission_gets_rank_one(self, session, wordle_game):
        result = record_submission(session, _make_result("user1"), username="Alice")
        assert result.submission_rank == 1

    def test_first_submission_gets_max_speed_bonus(self, session, wordle_game):
        result = record_submission(session, _make_result("user1"), username="Alice")
        assert result.speed_bonus == 15
        assert result.total_score == 75.0 + 15

    def test_second_submission_gets_rank_two(self, session, wordle_game):
        record_submission(session, _make_result("user1"), username="Alice")
        result = record_submission(session, _make_result("user2"), username="Bob")
        assert result.submission_rank == 2
        assert result.speed_bonus == 10

    def test_three_submissions_rank_and_bonus_assignment(self, session, wordle_game):
        r1 = record_submission(session, _make_result("user1"), username="Alice")
        r2 = record_submission(session, _make_result("user2"), username="Bob")
        r3 = record_submission(session, _make_result("user3"), username="Carol")

        assert (r1.submission_rank, r1.speed_bonus) == (1, 15)
        assert (r2.submission_rank, r2.speed_bonus) == (2, 10)
        assert (r3.submission_rank, r3.speed_bonus) == (3, 5)

    def test_fourth_submission_gets_no_speed_bonus(self, session, wordle_game):
        for uid, name in [("u1", "A"), ("u2", "B"), ("u3", "C")]:
            record_submission(session, _make_result(uid), username=name)
        r4 = record_submission(session, _make_result("u4"), username="D")
        assert r4.speed_bonus == 0

    def test_duplicate_returns_none(self, session, wordle_game):
        record_submission(session, _make_result("user1"), username="Alice")
        duplicate = record_submission(session, _make_result("user1"), username="Alice")
        assert duplicate is None

    def test_raw_data_preserved(self, session, wordle_game):
        result = record_submission(session, _make_result("user1"), username="Alice")
        assert result.raw_data == {"attempts": 3}


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------


class TestIsDuplicate:
    def test_returns_false_when_no_submission(self, session, wordle_game):
        assert not is_duplicate(session, "user1", "wordle", TODAY)

    def test_returns_true_after_submission(self, session, wordle_game):
        record_submission(session, _make_result("user1"), username="Alice")
        assert is_duplicate(session, "user1", "wordle", TODAY)

    def test_different_user_not_duplicate(self, session, wordle_game):
        record_submission(session, _make_result("user1"), username="Alice")
        assert not is_duplicate(session, "user2", "wordle", TODAY)

    def test_different_date_not_duplicate(self, session, wordle_game):
        record_submission(session, _make_result("user1"), username="Alice")
        assert not is_duplicate(session, "user1", "wordle", TODAY + timedelta(days=1))


# ---------------------------------------------------------------------------
# delete_submission
# ---------------------------------------------------------------------------


class TestDeleteSubmission:
    def test_removes_submission(self, session, wordle_game):
        r = record_submission(session, _make_result("user1"), username="Alice")
        delete_submission(session, r.id)
        assert session.get(Submission, r.id) is None

    def test_remaining_submissions_reranked(self, session, wordle_game):
        r1 = record_submission(session, _make_result("user1"), username="Alice")
        r2 = record_submission(session, _make_result("user2"), username="Bob")
        r3 = record_submission(session, _make_result("user3"), username="Carol")

        delete_submission(session, r1.id)
        session.refresh(r2)
        session.refresh(r3)

        assert r2.submission_rank == 1
        assert r2.speed_bonus == 15
        assert r3.submission_rank == 2
        assert r3.speed_bonus == 10

    def test_delete_nonexistent_is_noop(self, session, wordle_game):
        delete_submission(session, 999999)  # should not raise


# ---------------------------------------------------------------------------
# add_submission_manual
# ---------------------------------------------------------------------------


class TestAddSubmissionManual:
    def test_creates_submission(self, session, wordle_game):
        sub = add_submission_manual(
            session,
            user_id="user1",
            username="Alice",
            game_id="wordle",
            submission_date=TODAY,
            base_score=90.0,
            raw_data={"attempts": 2},
        )
        assert sub.id is not None
        assert sub.base_score == 90.0
        assert sub.submission_rank == 1
        assert sub.speed_bonus == 15

    def test_respects_custom_submitted_at(self, session, wordle_game):
        custom_time = datetime(2024, 1, 15, 8, 0, 0)
        sub = add_submission_manual(
            session,
            user_id="user1",
            username="Alice",
            game_id="wordle",
            submission_date=TODAY,
            base_score=60.0,
            raw_data={},
            submitted_at=custom_time,
        )
        assert sub.submitted_at == custom_time


# ---------------------------------------------------------------------------
# get_leaderboard
# ---------------------------------------------------------------------------


class TestGetLeaderboard:
    def test_alltime_returns_all_users(self, session, wordle_game):
        record_submission(
            session, _make_result("user1", base_score=100.0), username="Alice"
        )
        record_submission(
            session, _make_result("user2", base_score=80.0), username="Bob"
        )

        rows = get_leaderboard(session, "alltime")
        assert len(rows) == 2

    def test_alltime_ordered_by_total_score_desc(self, session, wordle_game):
        record_submission(
            session, _make_result("user1", base_score=100.0), username="Alice"
        )
        record_submission(
            session, _make_result("user2", base_score=80.0), username="Bob"
        )

        rows = get_leaderboard(session, "alltime")
        # user1 has higher base + higher speed bonus (submitted first)
        assert rows[0].username == "Alice"
        assert rows[1].username == "Bob"

    def test_ranks_are_sequential(self, session, wordle_game):
        record_submission(
            session, _make_result("user1", base_score=100.0), username="Alice"
        )
        record_submission(
            session, _make_result("user2", base_score=80.0), username="Bob"
        )

        rows = get_leaderboard(session, "alltime")
        assert [r.rank for r in rows] == [1, 2]

    def test_submission_count_is_correct(self, session, wordle_game):
        record_submission(
            session, _make_result("user1", base_score=75.0), username="Alice"
        )

        rows = get_leaderboard(session, "alltime")
        alice = next(r for r in rows if r.username == "Alice")
        assert alice.submission_count == 1

    def test_filter_by_game_id(self, session, wordle_game):
        glyph_game = Game(
            id="glyph",
            name="Glyph",
            enabled=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(glyph_game)
        session.flush()

        record_submission(
            session, _make_result("user1", game_id="wordle"), username="Alice"
        )
        record_submission(
            session,
            ParseResult(
                game_id="glyph",
                user_id="user2",
                date=TODAY,
                base_score=90.0,
                raw_data={},
            ),
            username="Bob",
        )

        rows = get_leaderboard(session, "alltime", game_id="glyph")
        assert len(rows) == 1
        assert rows[0].username == "Bob"

    def test_empty_db_returns_empty_list(self, session, wordle_game):
        rows = get_leaderboard(session, "alltime")
        assert rows == []


# ---------------------------------------------------------------------------
# get_streak / get_all_streaks
# ---------------------------------------------------------------------------


def _add(session, user_id, username, days_ago, game_id="wordle"):
    upsert_user(session, user_id, username)
    target_date = datetime.now(timezone.utc).date() - timedelta(days=days_ago)
    sub = Submission(
        user_id=user_id,
        username=username,
        game_id=game_id,
        date=target_date,
        base_score=75.0,
        speed_bonus=0,
        total_score=75.0,
        submission_rank=1,
        raw_data={},
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(sub)
    session.flush()
    update_streak_on_submission(session, user_id, game_id, target_date)
    return sub


class TestGetStreak:
    def test_zero_when_no_submissions(self, session, wordle_game):
        assert get_streak(session, "user1", "wordle") == 0

    def test_single_day_streak_today(self, session, wordle_game):
        _add(session, "user1", "Alice", days_ago=0)
        assert get_streak(session, "user1", "wordle") == 1

    def test_single_day_streak_yesterday(self, session, wordle_game):
        _add(session, "user1", "Alice", days_ago=1)
        assert get_streak(session, "user1", "wordle") == 1

    def test_multi_day_streak(self, session, wordle_game):
        # Add oldest first so streak increments correctly
        for d in range(3, -1, -1):
            _add(session, "user1", "Alice", days_ago=d)
        assert get_streak(session, "user1", "wordle") == 4

    def test_broken_streak_resets(self, session, wordle_game):
        # days 5,4,3 present, day 2 missing, days 1,0 present
        for d in [5, 4, 3, 1, 0]:
            _add(session, "user1", "Alice", days_ago=d)
        assert get_streak(session, "user1", "wordle") == 2

    def test_streak_ended_two_days_ago_returns_zero(self, session, wordle_game):
        # Most recent submission is 2 days ago — streak is inactive
        _add(session, "user1", "Alice", days_ago=2)
        assert get_streak(session, "user1", "wordle") == 0

    def test_different_game_not_counted(self, session, wordle_game):
        other_game = Game(
            id="connections",
            name="Connections",
            enabled=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.merge(other_game)
        session.flush()
        _add(session, "user1", "Alice", days_ago=0, game_id="connections")
        assert get_streak(session, "user1", "wordle") == 0


class TestGetAllStreaks:
    def test_returns_all_users_sorted_descending(self, session, wordle_game):
        # Alice: 3-day streak (add oldest first), Bob: 1-day streak
        for d in range(2, -1, -1):
            _add(session, "user1", "Alice", days_ago=d)
        _add(session, "user2", "Bob", days_ago=0)

        results = get_all_streaks(session, "wordle")
        assert len(results) == 2
        assert results[0] == ("user1", "Alice", 3)
        assert results[1] == ("user2", "Bob", 1)

    def test_empty_when_no_submissions(self, session, wordle_game):
        assert get_all_streaks(session, "wordle") == []

    def test_zero_streak_user_included(self, session, wordle_game):
        # User submitted but streak has lapsed (2 days ago)
        _add(session, "user1", "Alice", days_ago=2)
        results = get_all_streaks(session, "wordle")
        assert len(results) == 1
        assert results[0][2] == 0
