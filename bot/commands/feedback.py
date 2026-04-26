import logging

import discord
from discord import app_commands

from bot.config import ADMIN_DISCORD_IDS
from bot.database import add_feedback, log_usage_event

log = logging.getLogger(__name__)

_CATEGORIES = ["Bug Report", "Feature Request", "General Feedback", "Other"]


class FeedbackModal(discord.ui.Modal, title="Leave Feedback"):
    content = discord.ui.TextInput(
        label="Your feedback",
        style=discord.TextStyle.paragraph,
        placeholder="Tell us what's on your mind...",
        min_length=10,
        max_length=1000,
    )

    def __init__(self, category: str, session_factory) -> None:
        super().__init__()
        self._category = category
        self._session_factory = session_factory

    async def on_submit(self, interaction: discord.Interaction) -> None:
        with self._session_factory() as session:
            add_feedback(
                session,
                user_id=str(interaction.user.id),
                username=interaction.user.display_name,
                category=self._category,
                content=self.content.value,
            )
            log_usage_event(
                session,
                "command.feedback",
                str(interaction.user.id),
                interaction.user.display_name,
                {"category": self._category},
            )
            session.commit()

        log.info("/feedback submitted by %s [%s]", interaction.user.display_name, self._category)
        await interaction.response.send_message(
            "Thanks for your feedback! The admins have been notified.", ephemeral=True
        )
        await _notify_admins(interaction.client, interaction.user, self._category, self.content.value)


class _CategorySelect(discord.ui.Select):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        options = [discord.SelectOption(label=cat) for cat in _CATEGORIES]
        super().__init__(placeholder="Choose a category...", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        modal = FeedbackModal(category=self.values[0], session_factory=self._session_factory)
        await interaction.response.send_modal(modal)


class _FeedbackView(discord.ui.View):
    def __init__(self, session_factory) -> None:
        super().__init__(timeout=600)
        self.add_item(_CategorySelect(session_factory))


async def _notify_admins(
    client: discord.Client,
    submitter: discord.User,
    category: str,
    content: str,
) -> None:
    for admin_id in ADMIN_DISCORD_IDS:
        try:
            admin = await client.fetch_user(int(admin_id))
            await admin.send(
                f"**New feedback received** from **{submitter.display_name}**\n**Category:** {category}\n\n{content}"
            )
        except Exception:
            log.warning("Could not DM admin %s about new feedback", admin_id)


def register(tree: app_commands.CommandTree, registry, Session) -> None:
    @tree.command(name="feedback", description="Send feedback about the bot")
    async def feedback(interaction: discord.Interaction) -> None:
        try:
            view = _FeedbackView(session_factory=Session)
            await interaction.user.send(
                "We'd love to hear from you! Select a category below:",
                view=view,
            )
            await interaction.response.send_message(
                "Check your DMs — I've sent you a feedback form.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I couldn't DM you. Please enable DMs from server members and try again.",
                ephemeral=True,
            )
        log.info("/feedback invoked by %s", interaction.user.display_name)
