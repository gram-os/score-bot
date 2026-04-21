import pytest

from bot.scoring import calculate_speed_bonus


class TestCalculateSpeedBonus:
    def test_first_place(self):
        assert calculate_speed_bonus(1) == 15

    def test_second_place(self):
        assert calculate_speed_bonus(2) == 10

    def test_third_place(self):
        assert calculate_speed_bonus(3) == 5

    def test_fourth_place_no_bonus(self):
        assert calculate_speed_bonus(4) == 0

    def test_high_rank_no_bonus(self):
        assert calculate_speed_bonus(100) == 0
