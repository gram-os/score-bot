import os
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    submissions: Mapped[list["Submission"]] = relationship("Submission", back_populates="game")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("user_id", "game_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    base_score: Mapped[float] = mapped_column(Float, nullable=False)
    speed_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    submission_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    message_text: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    game: Mapped["Game"] = relationship("Game", back_populates="submissions")


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    remind_streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DailyPoll(Base):
    __tablename__ = "daily_polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_id: Mapped[str] = mapped_column(String, nullable=False)
    is_yes_no: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    suggestions: Mapped[list["GameSuggestion"]] = relationship("GameSuggestion", back_populates="poll")


class GameSuggestion(Base):
    __tablename__ = "game_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    game_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    poll_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("daily_polls.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    poll: Mapped["DailyPoll | None"] = relationship("DailyPoll", back_populates="suggestions")


class UserStreak(Base):
    __tablename__ = "user_streaks"
    __table_args__ = (UniqueConstraint("user_id", "game_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"), nullable=False)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    freeze_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    achievement_slug: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AppLog(Base):
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False)
    logger: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    exc_text: Mapped[str | None] = mapped_column(String, nullable=True)


class AdminConfig(Base):
    __tablename__ = "admin_config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class HomunculusUpgrade(Base):
    __tablename__ = "homunculus_upgrades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upgrade_text: Mapped[str] = mapped_column(String, nullable=False)
    vote_count: Mapped[int] = mapped_column(Integer, nullable=False)
    poll_question: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


def get_engine(db_path: str | None = None):
    path = db_path or os.environ.get("DATABASE_PATH", "/data/scores.db")
    return create_engine(f"sqlite:///{path}")
