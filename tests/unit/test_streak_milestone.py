import pytest

from bot.tasks.message_handler import _streak_milestone_hit


@pytest.mark.unit
@pytest.mark.parametrize(
    "streak, expected",
    [
        (6, None),
        (7, 7),
        (8, None),
        (14, 14),
        (100, 100),
        (101, None),
    ],
)
def test_streak_milestone_hit(streak: int, expected: int | None) -> None:
    assert _streak_milestone_hit(streak) == expected
