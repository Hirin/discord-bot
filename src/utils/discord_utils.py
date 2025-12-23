"""
Discord Utilities
"""

import asyncio
from typing import Union

import discord


async def send_chunked(
    target: Union[discord.Interaction, discord.TextChannel],
    text: str,
    chunk_size: int = 1900,  # Slightly less than 2000 for safety
) -> None:
    """
    Send a long message in chunks to avoid Discord's 2000 char limit.
    Splits by newlines to keep text coherent.
    """
    if not text:
        return

    chunks = []
    current_chunk = ""
    
    # split by lines to avoid cutting sentences
    lines = text.split('\n')
    
    for line in lines:
        # If line itself is too long, we must split it by chars
        if len(line) > chunk_size:
            # If we have content pending, flush it first
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # Split long line
            for i in range(0, len(line), chunk_size):
                chunks.append(line[i : i + chunk_size])
            continue
            
        # Check if adding this line would exceed chunk size
        # +1 for newline character that was stripped by split
        if len(current_chunk) + len(line) + 1 > chunk_size:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            if current_chunk:
                current_chunk += "\n" + line
            else:
                current_chunk = line
    
    if current_chunk:
        chunks.append(current_chunk)

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
            
        if isinstance(target, discord.Interaction):
            if i == 0 and not target.response.is_done():
                await target.response.send_message(chunk)
            else:
                await target.followup.send(chunk)
        else:
            await target.send(chunk)

        # Rate limit protection
        if i < len(chunks) - 1:
            await asyncio.sleep(0.5)
