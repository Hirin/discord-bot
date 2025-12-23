"""
Config Command - Single command with action dropdown
/config <action> [value]
"""

import discord
from discord import app_commands
from discord.ext import commands

from services import config as config_service


class ConfigModal(discord.ui.Modal, title="Set Custom Prompt"):
    """Modal for entering custom prompt"""

    prompt = discord.ui.TextInput(
        label="Custom Prompt",
        style=discord.TextStyle.paragraph,
        placeholder="Bạn là trợ lý tóm tắt cuộc họp...",
        max_length=2000,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        config_service.set_guild_config(
            self.guild_id, "custom_prompt", self.prompt.value
        )
        await interaction.response.send_message(
            f"✅ Custom prompt đã lưu!\n```{self.prompt.value[:200]}...```",
            ephemeral=True,
        )


class ApiModal(discord.ui.Modal, title="Set API Key"):
    """Modal for entering API key"""

    api_key = discord.ui.TextInput(
        label="API Key",
        style=discord.TextStyle.short,
        placeholder="Enter your API key",
    )

    def __init__(self, guild_id: int, key_type: str):
        super().__init__()
        self.guild_id = guild_id
        self.key_type = key_type

    async def on_submit(self, interaction: discord.Interaction):
        config_service.set_guild_config(
            self.guild_id, f"{self.key_type}_api_key", self.api_key.value
        )
        await interaction.response.send_message(
            f"✅ {self.key_type.upper()} API key đã lưu!",
            ephemeral=True,
        )


class TimezoneModal(discord.ui.Modal, title="Set Timezone"):
    """Modal for setting timezone"""

    timezone = discord.ui.TextInput(
        label="Timezone (UTC offset hoặc IANA)",
        style=discord.TextStyle.short,
        placeholder="UTC+7, UTC-5, Asia/Ho_Chi_Minh",
        default="UTC+7",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        from datetime import timezone as tz_module, timedelta
        from zoneinfo import ZoneInfo
        
        tz_name = self.timezone.value.strip()
        
        # Validate timezone - support both UTC+X and IANA format
        try:
            if tz_name.upper().startswith("UTC"):
                # Parse UTC+7 or UTC-5 format
                offset_str = tz_name[3:]
                if offset_str:
                    offset_hours = int(offset_str)
                else:
                    offset_hours = 0
                # Validate by creating timezone
                tz_module(timedelta(hours=offset_hours))
            else:
                # IANA format
                ZoneInfo(tz_name)
        except Exception:
            await interaction.response.send_message(
                f"❌ Timezone không hợp lệ: `{tz_name}`\n"
                "Dùng format: UTC+7, UTC-5, hoặc Asia/Ho_Chi_Minh",
                ephemeral=True,
            )
            return
        
        config_service.set_timezone(self.guild_id, tz_name)
        await interaction.response.send_message(
            f"✅ Timezone đã set: `{tz_name}`",
            ephemeral=True,
        )


class FirefliesLimitModal(discord.ui.Modal, title="Fireflies Storage Limit"):
    """Modal for setting max Fireflies records"""

    limit = discord.ui.TextInput(
        label="Max records (1-50, default 6)",
        style=discord.TextStyle.short,
        placeholder="6",
        default="6",
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit_val = int(self.limit.value.strip())
            if not 1 <= limit_val <= 50:
                raise ValueError("Out of range")
        except ValueError:
            await interaction.response.send_message(
                "❌ Số không hợp lệ. Nhập 1-50.",
                ephemeral=True,
            )
            return
        
        config_service.set_fireflies_max_records(self.guild_id, limit_val)
        await interaction.response.send_message(
            f"✅ Fireflies storage limit: `{limit_val}` records",
            ephemeral=True,
        )


class ConfigView(discord.ui.View):
    """Dropdown view for config actions"""

    def __init__(self, guild_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.select(
        placeholder="Chọn action...",
        options=[
            discord.SelectOption(label="Set GLM API Key", value="api_glm"),
            discord.SelectOption(label="Set Fireflies API Key", value="api_fireflies"),
            discord.SelectOption(label="Custom Prompt", value="prompt_set"),
            discord.SelectOption(label="View Prompt", value="prompt_view"),
            discord.SelectOption(label="Reset Prompt", value="prompt_reset"),
            discord.SelectOption(label="View Config", value="info"),
            discord.SelectOption(
                label="Set This Channel For Meetings", value="set_channel"
            ),
            discord.SelectOption(
                label="Custom Timezone", value="timezone"
            ),
            discord.SelectOption(
                label="📁 Set Archive Channel", value="set_archive"
            ),
            discord.SelectOption(
                label="📼 Fireflies Storage Limit", value="ff_limit"
            ),
            discord.SelectOption(
                label="🔄 Sync Commands", value="sync_commands"
            ),
        ],
    )
    async def select_action(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        action = select.values[0]

        if action == "api_glm":
            await interaction.response.send_modal(ApiModal(self.guild_id, "glm"))

        elif action == "api_fireflies":
            await interaction.response.send_modal(ApiModal(self.guild_id, "fireflies"))

        elif action == "prompt_set":
            await interaction.response.send_modal(ConfigModal(self.guild_id))

        elif action == "prompt_view":
            prompt = config_service.get_custom_prompt(self.guild_id)
            is_custom = bool(
                config_service.get_guild_config(self.guild_id).get("custom_prompt")
            )
            await interaction.response.send_message(
                f"**{'Custom' if is_custom else 'Default'} Prompt:**\n```{prompt[:1500]}```",
                ephemeral=True,
            )

        elif action == "prompt_reset":
            config_service.set_guild_config(self.guild_id, "custom_prompt", "")
            await interaction.response.send_message(
                "✅ Reset về prompt mặc định!", ephemeral=True
            )

        elif action == "info":
            config = config_service.get_guild_config(self.guild_id)
            glm = config.get("glm_api_key")
            ff = config.get("fireflies_api_key")
            has_prompt = bool(config.get("custom_prompt"))
            channel_id = config.get("meetings_channel")
            timezone = config_service.get_timezone(self.guild_id)

            embed = discord.Embed(title="⚙️ Server Config", color=discord.Color.blue())
            embed.add_field(
                name="API Keys",
                value=f"GLM: {'✅' if glm else '❌'} | Fireflies: {'✅' if ff else '❌'}",
                inline=False,
            )
            embed.add_field(
                name="Prompt",
                value="Custom ✅" if has_prompt else "Default",
                inline=True,
            )
            embed.add_field(
                name="Timezone",
                value=f"`{timezone}`",
                inline=True,
            )
            embed.add_field(
                name="Meetings Channel",
                value=f"<#{channel_id}>" if channel_id else "Not set",
                inline=True,
            )
            archive_id = config_service.get_archive_channel(self.guild_id)
            embed.add_field(
                name="Archive Channel",
                value=f"<#{archive_id}>" if archive_id else "Not set",
                inline=True,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif action == "set_channel":
            # Set current channel as meetings channel
            config_service.set_meetings_channel(self.guild_id, interaction.channel_id)
            await interaction.response.send_message(
                f"✅ Đã set kênh này làm Meetings Channel!\n"
                f"Bot sẽ tự động gửi summary vào <#{interaction.channel_id}>",
                ephemeral=True,
            )

        elif action == "timezone":
            await interaction.response.send_modal(TimezoneModal(self.guild_id))

        elif action == "set_archive":
            # Set current channel as archive channel
            config_service.set_archive_channel(self.guild_id, interaction.channel_id)
            await interaction.response.send_message(
                f"✅ Đã set kênh này làm Archive Channel!\n"
                f"Transcripts sẽ được backup vào <#{interaction.channel_id}>",
                ephemeral=True,
            )

        elif action == "ff_limit":
            await interaction.response.send_modal(FirefliesLimitModal(self.guild_id))

        elif action == "sync_commands":
            # Sync commands to this guild
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                bot = interaction.client
                guild = interaction.guild
                bot.tree.copy_global_to(guild=guild)
                await bot.tree.sync(guild=guild)
                await interaction.followup.send(
                    "✅ Đã sync commands cho server này!",
                    ephemeral=True,
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Lỗi sync: {str(e)[:100]}",
                    ephemeral=True,
                )

    @discord.ui.button(label="🔄 Reload", style=discord.ButtonStyle.secondary, row=1)
    async def reload_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Reload the dropdown view"""
        await interaction.response.edit_message(view=ConfigView(self.guild_id))

    @discord.ui.button(label="❌ Đóng", style=discord.ButtonStyle.danger, row=1)
    async def close_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Delete the message"""
        await interaction.message.delete()


class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="config", description="Server configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        """Show config options"""
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ Chỉ dùng trong server", ephemeral=True
            )
            return

        # Delete previous dropdown for this user
        user_id = interaction.user.id
        if user_id in self.bot.active_dropdowns:
            try:
                await self.bot.active_dropdowns[user_id].delete()
            except Exception:
                pass

        view = ConfigView(interaction.guild_id)
        await interaction.response.send_message(
            "⚙️ **Server Config** - Chọn action:",
            view=view,
            delete_after=60,
        )

        # Store this message
        self.bot.active_dropdowns[user_id] = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))
