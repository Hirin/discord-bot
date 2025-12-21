"""
Fireflies Scraper Service
Scrape transcripts from Fireflies.ai shared links
"""

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


async def scrape_fireflies(
    url: str, timeout: int = 60, retries: int = 3
) -> Optional[list[dict]]:
    """
    Scrape transcript from Fireflies.ai shared link.

    Args:
        url: Fireflies shared meeting URL
        timeout: Timeout in seconds
        retries: Number of retry attempts

    Returns:
        List of dicts with 'name', 'time', 'content' or None if failed
    """
    from playwright.async_api import async_playwright

    for attempt in range(retries):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                logger.info(
                    f"Scraping Fireflies (attempt {attempt + 1}): {url[:50]}..."
                )

                await page.goto(
                    url, wait_until="domcontentloaded", timeout=timeout * 1000
                )
                await page.wait_for_timeout(5000)

                # Close login modal if present
                try:
                    close_btn = page.locator("button.x, button.lciBA-d")
                    if await close_btn.count() > 0:
                        await close_btn.first.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Extract transcript from __NEXT_DATA__
                transcript_data = await page.evaluate("""
                    () => {
                        const pageProps = window.__NEXT_DATA__?.props?.pageProps || {};
                        const note = pageProps.initialMeetingNote;
                        
                        if (note && note.sentences) {
                            function formatTime(seconds) {
                                if (!seconds) return '00:00';
                                const mins = Math.floor(seconds / 60);
                                const secs = Math.floor(seconds % 60);
                                return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                            }
                            
                            return {
                                source: 'next_data',
                                data: note.sentences.map(s => ({
                                    name: s.speaker_name || 'Unknown',
                                    time: formatTime(s.start_time),
                                    content: s.text || ''
                                }))
                            };
                        }
                        
                        // Fallback: scrape from DOM
                        const containers = document.querySelectorAll('.sc-e4f1b385-1');
                        const container = containers[2] || containers[1] || containers[0];
                        if (container) {
                            const entries = [];
                            const text = container.innerText;
                            const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                            const tsRegex = /^\\d{1,2}:\\d{2}(:\\d{2})?$/;
                            
                            for (let i = 0; i < lines.length; i++) {
                                if (tsRegex.test(lines[i])) {
                                    const time = lines[i];
                                    let name = i > 0 ? lines[i-1] : 'Unknown';
                                    
                                    let content = '';
                                    let j = i + 1;
                                    while (j < lines.length) {
                                        if (tsRegex.test(lines[j])) break;
                                        if (j + 1 < lines.length && tsRegex.test(lines[j+1])) break;
                                        content += lines[j] + ' ';
                                        j++;
                                    }
                                    
                                    if (content.trim()) {
                                        entries.push({ name, time, content: content.trim() });
                                    }
                                }
                            }
                            
                            if (entries.length > 0) {
                                return { source: 'dom', data: entries };
                            }
                        }
                        
                        // Debug: return what we found
                        return { 
                            source: 'none', 
                            debug: {
                                hasNextData: !!window.__NEXT_DATA__,
                                hasPageProps: !!pageProps,
                                pagePropsKeys: Object.keys(pageProps),
                                hasInitialMeetingNote: !!note,
                                noteKeys: note ? Object.keys(note) : [],
                                hasSentences: !!(note && note.sentences),
                                sentencesLength: note && note.sentences ? note.sentences.length : 0
                            }
                        };
                    }
                """)

                await browser.close()

                if transcript_data and transcript_data.get("source") != "none":
                    logger.info(f"Transcript source: {transcript_data.get('source')}")
                    data = transcript_data.get("data", [])

                    # Clean trailing avatar initials
                    for entry in data:
                        content = entry["content"]
                        content = re.sub(r"[.!?,]? [A-Za-z]$", "", content)
                        entry["content"] = content.strip()

                    logger.info(f"Scraped {len(data)} entries")
                    return data

                # No data found - will retry
                debug_info = transcript_data.get("debug", {}) if transcript_data else {}
                logger.warning(
                    f"No transcript (attempt {attempt + 1}). Debug: {debug_info}"
                )

                if attempt < retries - 1:
                    backoff = 2**attempt
                    logger.info(f"Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    continue

        except Exception as e:
            logger.error(f"Scrape attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                backoff = 2**attempt
                logger.info(f"Retrying in {backoff}s...")
                await asyncio.sleep(backoff)

    return None


def format_transcript(entries: list[dict]) -> str:
    """Format transcript entries into readable text"""
    lines = []
    for entry in entries:
        lines.append(f"[{entry['time']}] {entry['name']}: {entry['content']}")
    return "\n".join(lines)
