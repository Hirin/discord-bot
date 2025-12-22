"""Meeting cog package"""

from .cog import Meeting


async def setup(bot):
    await bot.add_cog(Meeting(bot))
