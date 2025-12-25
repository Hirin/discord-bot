"""
Video Views for Lecture Command
Handles YouTube input, processing progress, and error handling
"""
import discord
import asyncio
import logging
import os
from typing import Optional

from services import gemini, video_download, video, lecture_cache, prompts
from services.video import format_timestamp, cleanup_files
from utils.discord_utils import send_chunked

logger = logging.getLogger(__name__)

RATE_LIMIT_WAIT = 60  # seconds between API calls


class LectureSourceView(discord.ui.View):
    """View with buttons to select Video or Transcript mode"""
    
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id
    
    @discord.ui.button(label="📹 Video (Gemini)", style=discord.ButtonStyle.success)
    async def video_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open video input modal"""
        modal = VideoInputModal(self.guild_id, self.user_id, interaction)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📝 Transcript (GLM)", style=discord.ButtonStyle.primary)
    async def transcript_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Use existing transcript flow from meeting cog"""
        from cogs.meeting.modals import MeetingIdModal
        modal = MeetingIdModal(self.guild_id, mode="lecture")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="❌ Đóng", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✅ Đã đóng", embed=None, view=None)


class VideoInputModal(discord.ui.Modal, title="Video Lecture Summary"):
    """Modal for entering video URL and title"""
    
    video_url = discord.ui.TextInput(
        label="Video URL",
        placeholder="Google Drive link hoặc direct URL (mp4)...",
        required=True,
    )
    
    lecture_title = discord.ui.TextInput(
        label="Tiêu đề bài giảng",
        placeholder="VD: M07W03 - Transformer",
        required=True,
        max_length=100,
    )
    
    def __init__(self, guild_id: int, user_id: int, parent_interaction: discord.Interaction):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id
        self.parent_interaction = parent_interaction
    
    async def on_submit(self, interaction: discord.Interaction):
        url = self.video_url.value.strip()
        title = self.lecture_title.value.strip()
        
        # Validate URL
        source_type, _ = video_download.validate_video_url(url)
        if source_type == 'invalid':
            await interaction.response.send_message(
                "❌ URL không hợp lệ. Hỗ trợ: Google Drive link hoặc direct video URL (mp4, webm...).",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Hide the source selection view
        try:
            await self.parent_interaction.edit_original_response(
                content=f"⏳ Đang xử lý: **{title}**",
                view=None
            )
        except Exception:
            pass  # Ignore if already edited
        
        # Start processing
        processor = VideoLectureProcessor(
            interaction=interaction,
            youtube_url=url,
            title=title,
            guild_id=self.guild_id,
            user_id=self.user_id,
        )
        await processor.process()


class VideoErrorView(discord.ui.View):
    """View with Retry / Change API Key / Close buttons for errors"""
    
    def __init__(self, processor: "VideoLectureProcessor"):
        super().__init__(timeout=600)
        self.processor = processor
    
    @discord.ui.button(label="🔄 Retry", style=discord.ButtonStyle.primary)
    async def retry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="🔄 Đang retry...", view=self)
        await self.processor.process(retry=True)
    
    @discord.ui.button(label="🔑 Đổi API Key", style=discord.ButtonStyle.secondary)
    async def change_api_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GeminiApiKeyModal(self.processor)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="❌ Đóng", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Cleanup any temp files
        self.processor.cleanup()
        await interaction.response.edit_message(content="✅ Đã đóng", view=None)


class GeminiApiKeyModal(discord.ui.Modal, title="Đổi Gemini API Key"):
    """Modal for entering new Gemini API key (saves to user config)"""
    
    api_key = discord.ui.TextInput(
        label="Gemini API Key",
        placeholder="AIza...",
        required=True,
    )
    
    def __init__(self, processor: "VideoLectureProcessor"):
        super().__init__()
        self.processor = processor
    
    async def on_submit(self, interaction: discord.Interaction):
        from services import config as config_service
        
        new_key = self.api_key.value.strip()
        
        # Save to user config (per-user)
        config_service.set_user_gemini_api(self.processor.user_id, new_key)
        
        # Also update env for current session
        os.environ["GOOGLE_API_KEY"] = new_key
        gemini._client = None
        
        await interaction.response.send_message(
            "✅ API Key đã lưu. Bạn có thể nhấn Retry.",
            ephemeral=True
        )


class VideoLectureProcessor:
    """Handles the full video processing pipeline"""
    
    def __init__(
        self,
        interaction: discord.Interaction,
        youtube_url: str,
        title: str,
        guild_id: int,
        user_id: int,
    ):
        self.interaction = interaction
        self.youtube_url = youtube_url
        self.title = title
        self.guild_id = guild_id
        self.user_id = user_id
        self.status_msg: Optional[discord.WebhookMessage] = None
        self.temp_files: list[str] = []
        self.lecture_id = lecture_cache.generate_lecture_id(youtube_url, guild_id)
    
    async def update_status(self, message: str):
        """Update the status message"""
        try:
            if self.status_msg:
                await self.status_msg.edit(content=message)
            else:
                self.status_msg = await self.interaction.followup.send(
                    message, ephemeral=True, wait=True
                )
        except Exception as e:
            logger.warning(f"Failed to update status: {e}")
    
    def cleanup(self):
        """Clean up temporary files"""
        cleanup_files(self.temp_files)
        self.temp_files = []
    
    async def process(self, retry: bool = False):
        """Main processing pipeline"""
        try:
            # Load user's API key
            from services import config as config_service
            user_api_key = config_service.get_user_gemini_api(self.user_id)
            if user_api_key:
                os.environ["GOOGLE_API_KEY"] = user_api_key
                gemini._client = None  # Reset to use new key
            
            # Check for cached summaries from previous attempt
            cached_parts = lecture_cache.get_cached_parts(self.lecture_id)
            if cached_parts and not retry:
                logger.info(f"Found {len(cached_parts)} cached parts for {self.lecture_id}")
            
            # Step 1: Download video
            await self.update_status("⏳ Đang tải video...")
            
            video_path = f"/tmp/lecture_{self.lecture_id}.mp4"
            if not os.path.exists(video_path) or retry:
                video_path = await video_download.download_video(
                    self.youtube_url, video_path
                )
            self.temp_files.append(video_path)
            
            # Step 2: Get video info and determine splits
            await self.update_status("⏳ Đang phân tích video...")
            
            info = await video.get_video_info(video_path)
            num_parts = video.calculate_num_parts(info.size_bytes)
            
            await self.update_status(
                f"⏳ Video: {format_timestamp(info.duration)} ({info.size_bytes // 1024 // 1024}MB) → {num_parts} phần"
            )
            
            # Step 3: Split video if needed
            if num_parts > 1:
                await self.update_status(f"⏳ Đang tách video thành {num_parts} phần...")
                parts = await video.split_video(video_path, num_parts)
                
                # Delete original video to save space
                cleanup_files([video_path])
                self.temp_files = [p["path"] for p in parts]
            else:
                parts = [{
                    "path": video_path,
                    "start_seconds": 0,
                    "duration": info.duration,
                }]
            
            # Step 4: Process each part
            summaries = []
            for i, part in enumerate(parts, 1):
                part_num = i
                
                # Check cache
                if part_num in cached_parts:
                    logger.info(f"Using cached summary for part {part_num}")
                    summaries.append(cached_parts[part_num]["summary"])
                    # Delete part video since we have cache
                    cleanup_files([part["path"]])
                    continue
                
                await self.update_status(
                    f"⏳ Đang xử lý phần {part_num}/{len(parts)} "
                    f"({format_timestamp(part['start_seconds'])} - {format_timestamp(part['start_seconds'] + part['duration'])})"
                )
                
                # Upload to Gemini
                gemini_file = await gemini.upload_video(part["path"])
                
                try:
                    # Generate summary
                    if part_num == 1:
                        prompt = prompts.GEMINI_LECTURE_PROMPT_PART1
                    else:
                        # Condense previous summaries for context
                        context = self._condense_summaries(summaries)
                        start_seconds = int(part["start_seconds"])
                        prompt = prompts.GEMINI_LECTURE_PROMPT_PART_N.format(
                            start_time=start_seconds,
                            previous_context=context,
                        )
                    
                    summary = await gemini.generate_lecture_summary(
                        gemini_file, prompt, guild_id=self.guild_id
                    )
                    
                    # Cache the summary
                    lecture_cache.save_part_summary(
                        self.lecture_id, part_num, summary, part["start_seconds"]
                    )
                    summaries.append(summary)
                    
                    # Delete part video after successful processing
                    cleanup_files([part["path"]])
                    self.temp_files.remove(part["path"])
                    
                finally:
                    # Always cleanup Gemini file
                    gemini.cleanup_file(gemini_file)
                
                # Wait between parts to avoid rate limit
                if part_num < len(parts):
                    await self.update_status(
                        f"⏳ Chờ {RATE_LIMIT_WAIT}s để tránh rate limit..."
                    )
                    await asyncio.sleep(RATE_LIMIT_WAIT)
            
            # Step 5: Merge summaries
            if len(summaries) > 1:
                await self.update_status("⏳ Đang tổng hợp các phần...")
                await asyncio.sleep(RATE_LIMIT_WAIT)  # Extra wait before merge
                
                final_summary = await gemini.merge_summaries(
                    summaries, prompts.GEMINI_MERGE_PROMPT
                )
            else:
                final_summary = summaries[0]
            
            # Post-process: Convert [-SECONDSs-] to clickable timestamp links
            final_summary = gemini.format_video_timestamps(final_summary, self.youtube_url)
            
            # Step 6: Send to channel
            header = f"🎓 **{self.title}**\n🔗 <{self.youtube_url}>\n\n"
            await send_chunked(self.interaction.channel, header + final_summary)
            
            # Cleanup cache and temp files
            lecture_cache.delete_cache(self.lecture_id)
            self.cleanup()
            
            await self.update_status("✅ Hoàn thành! Summary đã được gửi lên channel.")
            
        except Exception as e:
            logger.exception("Error in video lecture processing")
            
            # Show error with retry buttons
            error_view = VideoErrorView(self)
            error_msg = f"❌ Lỗi: {str(e)[:200]}"
            
            try:
                if self.status_msg:
                    await self.status_msg.edit(content=error_msg, view=error_view)
                else:
                    await self.interaction.followup.send(
                        error_msg, view=error_view, ephemeral=True
                    )
            except Exception:
                pass
    
    def _condense_summaries(self, summaries: list[str], max_chars: int = 2000) -> str:
        """Condense summaries for context in next part"""
        lines = []
        for summary in summaries:
            for line in summary.split('\n'):
                if line.startswith('## ') or line.startswith('- **'):
                    lines.append(line)
                    if len('\n'.join(lines)) > max_chars:
                        return '\n'.join(lines)
        return '\n'.join(lines)
