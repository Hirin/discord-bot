"""
Meeting Modals - UI modals for meeting actions
"""

import logging
from datetime import datetime, timedelta

import discord

from services import fireflies, fireflies_api, llm, scheduler, transcript_storage
from utils.discord_utils import send_chunked

logger = logging.getLogger(__name__)


class MeetingIdModal(discord.ui.Modal, title="Meeting Summary"):
    """Modal for entering meeting ID, local ID, or URL"""

    id_or_url = discord.ui.TextInput(
        label="Local ID, Fireflies ID, or URL",
        style=discord.TextStyle.short,
        placeholder="1452341542420484127_123456... hoặc 01K94... hoặc URL",
    )
    meeting_title = discord.ui.TextInput(
        label="Title (optional - for new)",
        style=discord.TextStyle.short,
        required=False,
        placeholder="Tên meeting (chỉ dùng cho meeting mới)",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        id_or_url = self.id_or_url.value.strip()

        try:
            # Check if it's a local ID first (format: guildid_hhmmssddmmyyyy)
            if "_" in id_or_url and not id_or_url.startswith("http"):
                # Try to get from local storage
                local_entry = transcript_storage.get_transcript(id_or_url)
                if local_entry:
                    title = local_entry.get("title", "Meeting")
                    # Always call LLM to regenerate summary
                    transcript_data = local_entry.get("transcript", [])
                    transcript_text = fireflies.format_transcript(transcript_data)
                    summary = await llm.summarize_transcript(
                        transcript_text, guild_id=self.guild_id
                    )
                    header = f"📋 **{title}** (ID: `{id_or_url}`)\n"
                    await send_chunked(interaction, header + summary)
                    return

            # Otherwise, treat as Fireflies ID or URL
            fireflies_id = None
            is_url = id_or_url.startswith("http")
            # Whitelist IDs that should NOT be auto-deleted (for testing)
            whitelist_ids = {"01K94BJAWM5JMFREPDXKJY16GB"}

            if is_url:
                if "fireflies.ai" not in id_or_url:
                    await interaction.followup.send("❌ Link không hợp lệ")
                    return
                # Scrape share link - don't auto delete (could be someone else's)
                transcript_data = await fireflies.scrape_fireflies(id_or_url)
                # Don't extract fireflies_id from URL - no auto delete for share links
            else:
                fireflies_id = id_or_url
                transcript_data = await fireflies_api.get_transcript_by_id(
                    id_or_url, guild_id=self.guild_id
                )

            if not transcript_data:
                await interaction.followup.send("❌ Không tìm thấy transcript")
                return

            # Generate summary
            transcript_text = fireflies.format_transcript(transcript_data)
            summary = await llm.summarize_transcript(
                transcript_text, guild_id=self.guild_id
            )


            # Auto save locally
            title = (
                self.meeting_title.value
                or f"Meeting {fireflies_id[:10] if fireflies_id else 'scraped'}"
            )
            entry = transcript_storage.save_transcript(
                guild_id=self.guild_id,
                fireflies_id=fireflies_id or "scraped",
                title=title,
                transcript_data=transcript_data,
            )

            # Auto delete from Fireflies if we have ID (not from URL, not whitelisted)
            if fireflies_id and fireflies_id not in whitelist_ids:
                await fireflies_api.delete_transcript(fireflies_id, self.guild_id)

            # Send summary + status
            header = f"📋 **{title}** (ID: `{entry['local_id']}`)\n"
            await send_chunked(interaction, header + summary)

        except Exception as e:
            logger.exception("Error in meeting summary")
            await interaction.followup.send(f"❌ Lỗi: {str(e)[:100]}")


class JoinMeetingModal(discord.ui.Modal, title="Join Meeting Now"):
    """Modal for joining a meeting immediately"""

    meeting_link = discord.ui.TextInput(
        label="Meeting Link",
        style=discord.TextStyle.short,
        placeholder="https://meet.google.com/xxx hoặc Zoom link",
    )
    meeting_title = discord.ui.TextInput(
        label="Title (optional)",
        style=discord.TextStyle.short,
        required=False,
        placeholder="Tên meeting",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        success, msg = await fireflies_api.add_to_live_meeting(
            meeting_link=self.meeting_link.value,
            guild_id=self.guild_id,
            title=self.meeting_title.value or None,
        )

        emoji = "✅" if success else "❌"
        await interaction.followup.send(f"{emoji} {msg}")


class ScheduleMeetingModal(discord.ui.Modal, title="Schedule Meeting"):
    """Modal for scheduling a meeting"""

    meeting_link = discord.ui.TextInput(
        label="Meeting Link",
        style=discord.TextStyle.short,
        placeholder="https://meet.google.com/xxx",
    )
    time_input = discord.ui.TextInput(
        label="Thời gian (HH:MM hoặc +30m)",
        style=discord.TextStyle.short,
        placeholder="14:30 hoặc +30m (sau 30 phút)",
    )
    meeting_title = discord.ui.TextInput(
        label="Title (optional)",
        style=discord.TextStyle.short,
        required=False,
        placeholder="Tên meeting",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        time_str = self.time_input.value.strip()
        now = datetime.now()

        try:
            # Parse time
            if time_str.startswith("+"):
                # Relative time: +30m, +1h
                value = time_str[1:-1]
                unit = time_str[-1].lower()
                if unit == "m":
                    scheduled_time = now + timedelta(minutes=int(value))
                elif unit == "h":
                    scheduled_time = now + timedelta(hours=int(value))
                else:
                    raise ValueError("Invalid time format")
            else:
                # Absolute time: HH:MM
                time_parts = time_str.split(":")
                scheduled_time = now.replace(
                    hour=int(time_parts[0]),
                    minute=int(time_parts[1]),
                    second=0,
                    microsecond=0,
                )
                # If time is in the past, assume tomorrow
                if scheduled_time < now:
                    scheduled_time += timedelta(days=1)

        except Exception:
            await interaction.response.send_message(
                "❌ Format thời gian không hợp lệ. Dùng HH:MM hoặc +30m",
                ephemeral=True,
            )
            return

        # Schedule the meeting
        entry = scheduler.add_scheduled(
            meeting_link=self.meeting_link.value,
            scheduled_time=scheduled_time,
            guild_id=self.guild_id,
            title=self.meeting_title.value or None,
        )

        await interaction.response.send_message(
            f"✅ Đã lên lịch!\n"
            f"**ID:** `{entry['id']}`\n"
            f"**Time:** {scheduled_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"**Link:** {self.meeting_link.value[:50]}...\n"
            f"_(Dùng View Scheduled để xem/xóa)_",
            delete_after=60,
        )


class CancelScheduleModal(discord.ui.Modal, title="Cancel Scheduled Meeting"):
    """Modal for canceling a scheduled meeting"""

    schedule_id = discord.ui.TextInput(
        label="Schedule ID",
        style=discord.TextStyle.short,
        placeholder="1452341542420484127_1734839580",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        schedule_id = self.schedule_id.value.strip()

        if scheduler.remove_scheduled(schedule_id):
            await interaction.response.send_message(
                f"✅ Đã hủy lịch `{schedule_id}`", delete_after=30
            )
        else:
            await interaction.response.send_message(
                f"❌ Không tìm thấy lịch `{schedule_id}`", ephemeral=True
            )


class SaveDeleteModal(discord.ui.Modal, title="Save & Delete from Fireflies"):
    """Modal for saving transcript locally and deleting from Fireflies"""

    fireflies_id = discord.ui.TextInput(
        label="Fireflies Transcript ID",
        style=discord.TextStyle.short,
        placeholder="01K94BJAWM5JMFREPDXKJY16GB",
    )
    meeting_title = discord.ui.TextInput(
        label="Title (optional)",
        style=discord.TextStyle.short,
        required=False,
        placeholder="Meeting title",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        ff_id = self.fireflies_id.value.strip()

        # Get transcript from Fireflies
        transcript_data = await fireflies_api.get_transcript_by_id(
            ff_id, guild_id=self.guild_id
        )

        if not transcript_data:
            await interaction.followup.send("❌ Không tìm thấy transcript")
            return

        # Generate summary
        transcript_text = fireflies.format_transcript(transcript_data)
        summary = await llm.summarize_transcript(
            transcript_text, guild_id=self.guild_id
        )

        # Save locally
        title = self.meeting_title.value or f"Meeting {ff_id[:10]}"
        entry = transcript_storage.save_transcript(
            guild_id=self.guild_id,
            fireflies_id=ff_id,
            title=title,
            transcript_data=transcript_data,
            summary=summary,
        )

        # Delete from Fireflies
        success, msg = await fireflies_api.delete_transcript(ff_id, self.guild_id)

        if success:
            await interaction.followup.send(
                f"✅ Đã lưu & xóa từ Fireflies!\n"
                f"**Local ID:** `{entry['local_id']}`\n"
                f"**Title:** {title}",
                delete_after=60,
            )
        else:
            await interaction.followup.send(
                f"✅ Đã lưu local (ID: `{entry['local_id']}`)\n"
                f"⚠️ Không xóa được từ FF: {msg}",
                delete_after=60,
            )


class DeleteSavedModal(discord.ui.Modal, title="Delete Saved Transcript"):
    """Modal for deleting a saved transcript"""

    local_id = discord.ui.TextInput(
        label="Local ID",
        style=discord.TextStyle.short,
        placeholder="1452341542420484127_103055221220",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        local_id = self.local_id.value.strip()

        if transcript_storage.delete_transcript(local_id):
            await interaction.response.send_message(
                f"✅ Đã xóa transcript `{local_id}`", delete_after=30
            )
        else:
            await interaction.response.send_message(
                f"❌ Không tìm thấy transcript `{local_id}`", ephemeral=True
            )
