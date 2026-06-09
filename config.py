import os

# ════════════════════════════════════════════════════════════
#   🎵 THRINO MUSIC BOT  ·  config.py
#
#   WHY TWO CLIENTS?
#   ─────────────────
#   Telegram bots (bot_token) CANNOT join voice chats.
#   Only real user accounts can.
#
#   So this bot runs TWO Pyrogram clients:
#     • bot    → handles commands (/play, /ban etc.)  [bot token]
#     • user   → actually joins voice chat & streams  [string session]
#
#   The "user" account is called the "assistant" in most music bots.
#   It should be a secondary/dedicated Telegram account.
# ════════════════════════════════════════════════════════════

class Config:
    # ── Telegram API credentials (same for both clients) ────
    # From https://my.telegram.org/apps
    API_ID   = int(os.environ.get("API_ID",   "0"))
    API_HASH =     os.environ.get("API_HASH",  "")

    # ── Bot token ────────────────────────────────────────────
    # From @BotFather → /newbot
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    # ── Pyrogram string session (USER ACCOUNT) ───────────────
    # Generate with:  python generate_session.py
    # This is the account that actually joins voice chats.
    # Use a secondary/dedicated Telegram account.
    STRING_SESSION = os.environ.get("STRING_SESSION", "")

    # ── Owner user ID ────────────────────────────────────────
    # Your personal Telegram user ID (from @userinfobot)
    OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

    # ── Bot username (without @) ─────────────────────────────
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "ThrinoMusicBot")

    # ── Support link ─────────────────────────────────────────
    SUPPORT = os.environ.get("SUPPORT", "https://t.me/yoursupportgroup")

    # ── YouTube cookies file ─────────────────────────────────
    # Place cookies.txt next to bot.py  (see INSTRUCTIONS.md)
    COOKIES_FILE = os.environ.get("COOKIES_FILE", "cookies.txt")

    # ── Downloads directory ──────────────────────────────────
    DL_DIR = "downloads"

    # ── Warn threshold before auto-ban ───────────────────────
    MAX_WARNS = 3
