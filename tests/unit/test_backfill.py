from datetime import date, datetime, timezone


from web.discord_api import date_to_snowflake, snowflake_to_datetime

DISCORD_EPOCH_MS = 1420070400000


class TestDateToSnowflake:
    def test_start_of_day(self):
        d = date(2024, 1, 15)
        snowflake = date_to_snowflake(d, end_of_day=False)
        expected_ms = int(datetime(2024, 1, 15, tzinfo=timezone.utc).timestamp() * 1000)
        assert snowflake == (expected_ms - DISCORD_EPOCH_MS) << 22

    def test_end_of_day(self):
        d = date(2024, 1, 15)
        snowflake = date_to_snowflake(d, end_of_day=True)
        expected_ms = int(datetime(2024, 1, 15, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)
        assert snowflake == (expected_ms - DISCORD_EPOCH_MS) << 22

    def test_end_of_day_greater_than_start(self):
        d = date(2024, 3, 10)
        assert date_to_snowflake(d, end_of_day=True) > date_to_snowflake(d, end_of_day=False)

    def test_later_date_produces_larger_snowflake(self):
        assert date_to_snowflake(date(2024, 6, 1)) > date_to_snowflake(date(2024, 1, 1))


class TestSnowflakeToDatetime:
    def test_roundtrip(self):
        d = date(2024, 4, 20)
        snowflake = date_to_snowflake(d, end_of_day=False)
        recovered = snowflake_to_datetime(snowflake)
        assert recovered.date() == d

    def test_returns_utc(self):
        snowflake = date_to_snowflake(date(2024, 1, 1))
        dt = snowflake_to_datetime(snowflake)
        assert dt.tzinfo == timezone.utc
