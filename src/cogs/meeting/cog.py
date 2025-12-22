"""
Meeting Cog - Main command and view for meeting management
"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from services import scheduler, transcript_storage

from .modals import (
    CancelScheduleModal,
    DeleteSavedModal,
    JoinMeetingModal,
    MeetingIdModal,
    ScheduleMeetingModal,
)

logger = logging.getLogger(__name__)


class MeetingView(discord.ui.View):
    """Dropdown view for meeting actions"""

    def __init__(self, guild_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        # Add link button for supported platforms
        self.add_item(
            discord.ui.Button(
                label="Supported Platforms",
                url="https://fireflies.ai/integrations",
                style=discord.ButtonStyle.link,
                row=1,
            )
        )

    @discord.ui.select(
        placeholder="Chọn action...",
        options=[
            discord.SelectOption(label="List Meetings", value="list"),
            discord.SelectOption(label="Summarize Meeting", value="summary"),
            discord.SelectOption(label="Join Now", value="join"),
            discord.SelectOption(label="Schedule Join", value="schedule"),
            discord.SelectOption(label="View Scheduled", value="view_scheduled"),
            discord.SelectOption(label="Cancel Schedule", value="cancel_schedule"),
            discord.SelectOption(label="Delete Transcript", value="delete_transcript"),
        ],
    )
    async def select_action(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        action = select.values[0]

        if action == "list":
            # List locally saved transcripts
            saved = transcript_storage.list_transcripts(self.guild_id, limit=10)

            if not saved:
                await interaction.response.send_message(
                    "📁 Chưa có transcript nào. Dùng Summarize để tạo.", ephemeral=True
                )
                return

            embed = discord.Embed(title="📋 List Meetings", color=discord.Color.blue())

            for t in saved:
                ts = t.get("created_timestamp")
                # Fallback: parse isoformat for old transcripts
                if not ts and t.get("created_at"):
                    try:
                        dt = datetime.fromisoformat(t["created_at"])
                        ts = int(dt.timestamp())
                    except Exception:
                        pass
                time_str = f"<t:{ts}:f>" if ts else "N/A"
                embed.add_field(
                    name=f"📝 {t.get('title', 'Untitled')[:40]}",
                    value=f"**ID:** `{t['local_id']}`\n{time_str}",
                    inline=False,
                )

            embed.set_footer(
                text="Dùng Summarize với ID để xem lại | Delete Transcript để xóa"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif action == "summary":
            await interaction.response.send_modal(MeetingIdModal(self.guild_id))

        elif action == "join":
            await interaction.response.send_modal(JoinMeetingModal(self.guild_id))

        elif action == "schedule":
            await interaction.response.send_modal(ScheduleMeetingModal(self.guild_id))

        elif action == "view_scheduled":
            scheduled = scheduler.get_scheduled_for_guild(self.guild_id)

            if not scheduled:
                await interaction.response.send_message(
                    "📅 Không có meeting nào được lên lịch.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📅 Scheduled Meetings", color=discord.Color.green()
            )
            for m in scheduled[:5]:
                time_str = m.get("scheduled_time", "")[:16]
                link = m.get("meeting_link", "")[:30]
                embed.add_field(
                    name=f"{m.get('title') or 'Meeting'}",
                    value=f"**ID:** `{m.get('id')}`\n**Time:** {time_str}\n**Link:** {link}...",
                    inline=False,
                )

            embed.set_footer(text="Dùng Cancel Schedule để hủy")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif action == "cancel_schedule":
            await interaction.response.send_modal(CancelScheduleModal(self.guild_id))

        elif action == "delete_transcript":
            await interaction.response.send_modal(DeleteSavedModal(self.guild_id))

    @discord.ui.button(label="🔄 Reload", style=discord.ButtonStyle.secondary, row=1)
    async def reload_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Reload the dropdown view"""
        await interaction.response.edit_message(view=MeetingView(self.guild_id))

    @discord.ui.button(label="❌ Đóng", style=discord.ButtonStyle.danger, row=1)
    async def close_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Delete the message"""
        await interaction.message.delete()


class Meeting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Start scheduler background task
        self.scheduler_task = bot.loop.create_task(scheduler.run_scheduler(bot))

    def cog_unload(self):
        self.scheduler_task.cancel()

    @app_commands.command(name="meeting", description="Meeting tools")
    async def meeting(self, interaction: discord.Interaction):
        """Show meeting options"""
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ Chỉ dùng trong server", ephemeral=True
            )
            return

        # Delete previous dropdown
        user_id = interaction.user.id
        if user_id in self.bot.active_dropdowns:
            try:
                await self.bot.active_dropdowns[user_id].delete()
            except Exception:
                pass

        view = MeetingView(interaction.guild_id)
        await interaction.response.send_message(
            "📋 **Meeting** - Chọn action:",
            view=view,
            delete_after=60,
        )

        self.bot.active_dropdowns[user_id] = await interaction.original_response()
