"""
Document Upload Views - UI components for document upload flow
"""

import asyncio
import logging

import discord

from services import llm
from utils.document_utils import pdf_to_images, validate_attachment

logger = logging.getLogger(__name__)


class DocumentPromptView(discord.ui.View):
    """Yes/No buttons for document upload prompt"""

    def __init__(self):
        super().__init__(timeout=60)  # 60s timeout for button click
        self.wants_doc = None
        self.doc_interaction = None

    @discord.ui.button(label="✅ Có", style=discord.ButtonStyle.success)
    async def yes_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.wants_doc = True
        self.doc_interaction = interaction
        await interaction.response.send_message(
            "📎 **Upload file PDF** trong 90s...\n"
            "_(Gửi file vào channel này)_",
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="❌ Không", style=discord.ButtonStyle.secondary)
    async def no_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.wants_doc = False
        await interaction.response.defer()
        self.stop()


async def prompt_for_document(
    interaction: discord.Interaction,
    bot,
    guild_id: int,
) -> str | None:
    """
    Prompt user for optional document upload and extract glossary.
    
    Args:
        interaction: Discord interaction (must be deferred)
        bot: Discord bot instance
        guild_id: Guild ID for API key
        
    Returns:
        Extracted glossary text or None
    """
    # Send prompt with buttons
    view = DocumentPromptView()
    prompt_msg = await interaction.followup.send(
        "📎 **Có bổ sung tài liệu?**\n"
        "Trích xuất glossary & key points để summary chi tiết hơn",
        view=view,
        ephemeral=True,
    )

    # Wait for button click or timeout
    await view.wait()

    # Clean up prompt message
    try:
        await prompt_msg.delete()
    except Exception:
        pass

    if not view.wants_doc:
        return None

    # Wait for file upload
    def check(m):
        return (
            m.author.id == interaction.user.id
            and m.channel.id == interaction.channel.id
            and m.attachments
        )

    try:
        msg = await bot.wait_for("message", check=check, timeout=90)
        attachment = msg.attachments[0]

        # Validate file
        is_valid, error = validate_attachment(attachment)
        if not is_valid:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return None

        # Download and process
        await interaction.followup.send("⏳ Đang xử lý tài liệu...", ephemeral=True)
        
        file_bytes = await attachment.read()
        images = pdf_to_images(file_bytes)

        if not images:
            await interaction.followup.send(
                "❌ Không thể đọc PDF", ephemeral=True
            )
            return None

        # Extract glossary using Vision model
        glossary = await llm.extract_glossary_vision(images, guild_id)

        # Clean up user's message with attachment
        try:
            await msg.delete()
        except Exception:
            pass

        if glossary:
            await interaction.followup.send(
                f"✅ Đã trích xuất glossary ({len(glossary)} chars)",
                ephemeral=True,
            )

        return glossary

    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⏰ Timeout - tiếp tục không có tài liệu",
            ephemeral=True,
        )
        return None
    except Exception as e:
        logger.exception("Error processing document")
        await interaction.followup.send(
            f"❌ Lỗi xử lý tài liệu: {str(e)[:50]}",
            ephemeral=True,
        )
        return None
