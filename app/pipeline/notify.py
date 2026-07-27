"""Telegram MarkdownV2 digest formatting and safe delivery."""
from __future__ import annotations

import asyncio
import logging

from telegram import Bot
from telegram.constants import ParseMode

from app.config import Settings
from app.db import Opportunity

logger = logging.getLogger(__name__)
_MARKDOWN_V2_RESERVED = "_*[]()~`>#+-=|{}.!"


def _escape(value: object) -> str:
    text = str(value or "unknown")
    return "".join(f"\\{character}" if character in _MARKDOWN_V2_RESERVED else character for character in text)


def _bullet_list(value: str | None) -> str:
    entries = [entry for entry in (value or "").split(" | ") if entry]
    return "\n".join(f"• {_escape(entry)}" for entry in entries[:5]) or "• No specific match details available"


def format_opportunity(item: Opportunity) -> str:
    apply_link = _escape(item.raw_url) if item.raw_url else "Not provided"
    return (
        "🚀 *NEW OPPORTUNITY*\n\n"
        f"*{_escape(item.title)}*\n\n"
        f"⭐ *Match Score:* {_escape(f'{item.suitability_score or 0:.0f}%')}\n"
        f"🏆 *Resume Value:* {_escape(item.resume_value)}\n"
        f"⏰ *Deadline:* {_escape(item.deadline)}\n"
        f"🎯 *Difficulty:* {_escape(item.difficulty)}\n\n"
        "*Why it fits*\n"
        f"{_bullet_list(item.suitability_reasons)}\n\n"
        "*Skills matched*\n"
        f"{_bullet_list(item.skills_matched)}\n\n"
        f"🔗 *Apply:* {apply_link}"
    )


def format_digest(items: list[Opportunity]) -> list[str]:
    """Return MarkdownV2 messages capped below Telegram's 4096-character limit."""
    if not items:
        return []
    messages: list[str] = []
    current = ""
    for item in items[:5]:
        block = format_opportunity(item)
        if current and len(current) + len(block) + 2 > 4096:
            messages.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        messages.append(current)
    return messages


async def _send(token: str, chat_id: str, messages: list[str]) -> None:
    async with Bot(token=token) as bot:
        for message in messages:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)


def send_digest(settings: Settings, items: list[Opportunity]) -> bool:
    if not items:
        return False
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials are not configured; digest was not sent")
        return False
    try:
        asyncio.run(_send(settings.telegram_bot_token, settings.telegram_chat_id, format_digest(items)))
        return True
    except Exception:
        logger.exception("Telegram digest failed")
        return False
