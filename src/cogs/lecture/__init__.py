"""Lecture Cog Package"""
from .cog import LectureCog


async def setup(bot):
    await bot.add_cog(LectureCog(bot))
