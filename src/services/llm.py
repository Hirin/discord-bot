"""
LLM Service - GLM API Client
Uses OpenAI-compatible client with Z.AI base URL
"""

import asyncio
import logging
import os
from typing import Optional

from openai import OpenAI

from services import config as config_service

logger = logging.getLogger(__name__)


def get_client(guild_id: Optional[int] = None) -> OpenAI:
    """Get configured OpenAI client for GLM API"""
    # Try guild-specific key first, then fallback to env
    if guild_id:
        api_key = config_service.get_api_key(guild_id, "glm")
    else:
        api_key = os.getenv("GLM_API_KEY")

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("GLM_BASE_URL", "https://api.z.ai/api/paas/v4/"),
    )


async def extract_glossary_vision(
    image_base64_list: list[str],
    guild_id: Optional[int] = None,
    timeout: int = 120,
    retries: int = 3,
) -> Optional[str]:
    """
    Extract glossary and key terms from document images using GLM-4.6V-Flash.

    Args:
        image_base64_list: List of base64 encoded PNG images
        guild_id: Guild ID for guild-specific API key
        timeout: Timeout in seconds
        retries: Number of retry attempts

    Returns:
        Extracted glossary text or None if failed
    """
    if not image_base64_list:
        return None

    model = os.getenv("GLM_VISION_MODEL", "glm-4.6v-flash")
    client = get_client(guild_id)

    # Build content with images (GLM-4.6V supports up to 200 pages)
    content = []
    for img in image_base64_list:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img}"}
        })

    content.append({
        "type": "text",
        "text": """Đây là slides/tài liệu của một buổi họp/presentation.

Hãy trích xuất NỘI DUNG CHÍNH từ các slides này:

**Quy tắc:**
- BỎ QUA các slide không có nội dung thực sự (slide tiêu đề, slide "Thank you", slide chỉ có hình ảnh không liên quan)
- CHỈ trích xuất thông tin có giá trị, actionable
- Gộp các thông tin liên quan lại với nhau

**Format output:**
## Chủ đề: [Tên chủ đề chính]

### Nội dung chính
- Điểm 1
- Điểm 2
...

### Phân công công việc (nếu có)
- [Tên người]: Task cụ thể - Deadline

### Thông tin khác
- Các chi tiết quan trọng khác

Trích xuất đầy đủ các thông tin quan trọng."""
    })

    for attempt in range(retries):
        try:
            logger.info(f"Extracting glossary from {len(image_base64_list)} pages (attempt {attempt + 1})...")

            loop = asyncio.get_event_loop()
            completion = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": content}],
                    timeout=timeout,
                    extra_body={"thinking": {"type": "enabled"}},
                ),
            )

            glossary = completion.choices[0].message.content
            logger.info(f"Glossary extracted: {len(glossary)} chars")
            return glossary

        except Exception as e:
            logger.error(f"Vision attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                backoff = 5 * (attempt + 1)  # 5s, 10s, 15s
                logger.info(f"Retrying in {backoff}s...")
                await asyncio.sleep(backoff)

    return None


async def summarize_transcript(
    transcript: str,
    guild_id: Optional[int] = None,
    glossary: Optional[str] = None,
    timeout: int = 60,
    retries: int = 3,
) -> Optional[str]:
    """
    Summarize a meeting transcript using GLM API.

    Args:
        transcript: Full transcript text
        guild_id: Guild ID for guild-specific API key
        glossary: Optional glossary/context from uploaded document
        timeout: Timeout in seconds
        retries: Number of retry attempts

    Returns:
        Summary text or error message
    """
    model = os.getenv("GLM_MODEL", "glm-4.6")
    client = get_client(guild_id)

    # Get custom prompt or default
    system_prompt = (
        config_service.get_custom_prompt(guild_id)
        if guild_id
        else config_service.DEFAULT_PROMPT
    )

    # Inject glossary context if provided
    if glossary:
        system_prompt += f"\n\n## Tài liệu tham khảo:\n{glossary[:5000]}"

    last_error = "Unknown error"
    for attempt in range(retries):
        try:
            logger.info(f"Summarizing transcript (attempt {attempt + 1})...")

            # Run sync client in thread pool
            loop = asyncio.get_event_loop()
            completion = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"Tóm tắt cuộc họp sau:\n\n{transcript[:15000]}",
                        },  # Limit context
                    ],
                    timeout=timeout,
                    extra_body={"thinking": {"type": "enabled"}},
                ),
            )

            summary = completion.choices[0].message.content
            logger.info(f"Summary generated: {len(summary)} chars")
            return summary

        except Exception as e:
            last_error = str(e)
            logger.error(f"LLM attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                backoff = 5 * (attempt + 1)  # 5s, 10s, 15s
                logger.info(f"Retrying in {backoff}s...")
                await asyncio.sleep(backoff)

    # Return error message instead of None
    return f"⚠️ LLM Error: {last_error[:200]}"
