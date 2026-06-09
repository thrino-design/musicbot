"""
╔══════════════════════════════════════════════════════════════╗
║           🎵  T H R I N O   M U S I C   B O T               ║
║          Voice Chat  +  Group Manager  +  More               ║
║                                                               ║
║  Architecture (READ THIS):                                    ║
║  ──────────────────────────                                   ║
║  This bot uses TWO Pyrogram clients:                          ║
║                                                               ║
║  1. `bot`   → bot account  → handles /commands               ║
║  2. `user`  → user account → joins VC and streams music      ║
║                                                               ║
║  Regular bot accounts CANNOT join voice chats.               ║
║  That is a Telegram limitation, not a code problem.          ║
║  The `user` client uses a Pyrogram STRING_SESSION.           ║
║                                                               ║
║  Stack:  Pyrogram 2.x  +  py-tgcalls (latest)  +  yt-dlp    ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, re, asyncio, logging
from functools import wraps
from flask import Flask
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPermissions,
)
from pyrogram.errors import ChatAdminRequired, UserAdminInvalid

from pytgcalls import PyTgCalls, idle
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError

from config import Config
from queue_manager import Q
from ytdl import search_one, search_many, get_info, download_audio, fmt_dur


# ════════════════════════════════════════════════════════════
#   LOGGING
# ════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("thrino")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()

# ════════════════════════════════════════════════════════════
#   CLIENT SETUP
#   bot   = bot account  (handles commands)
#   user  = user account (joins voice chats - REQUIRED)
#   calls = PyTgCalls wrapping the USER client
# ════════════════════════════════════════════════════════════

bot = Client(
    name      = "thrino_bot",
    api_id    = Config.API_ID,
    api_hash  = Config.API_HASH,
    bot_token = Config.BOT_TOKEN,
)

user = Client(
    name           = "thrino_user",
    api_id         = Config.API_ID,
    api_hash       = Config.API_HASH,
    session_string = Config.STRING_SESSION,
)

# PyTgCalls wraps the USER client (not the bot)
calls = PyTgCalls(user)

# ════════════════════════════════════════════════════════════
#   UTILS
# ════════════════════════════════════════════════════════════

async def is_admin(chat_id: int, user_id: int) -> bool:
    if user_id == Config.OWNER_ID:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def resolve_target(client: Client, msg: Message):
    """Get target user from reply or @mention argument."""
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user
    if len(msg.command) > 1:
        try:
            return await client.get_users(msg.command[1].lstrip("@"))
        except Exception:
            pass
    return None


def player_kb(cid: int) -> InlineKeyboardMarkup:
    loop_emoji = "🔁" if Q.is_loop(cid) else "➡️"
    vol = Q.get_volume(cid)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause",   callback_data=f"vc|pause|{cid}"),
            InlineKeyboardButton("▶️ Resume",  callback_data=f"vc|resume|{cid}"),
            InlineKeyboardButton("⏭ Skip",    callback_data=f"vc|skip|{cid}"),
        ],
        [
            InlineKeyboardButton("🔉 −10",     callback_data=f"vc|vdn|{cid}"),
            InlineKeyboardButton(f"🔊 {vol}%", callback_data=f"vc|vol|{cid}"),
            InlineKeyboardButton("🔊 +10",     callback_data=f"vc|vup|{cid}"),
        ],
        [
            InlineKeyboardButton(f"{loop_emoji} Loop", callback_data=f"vc|loop|{cid}"),
            InlineKeyboardButton("⏹ Stop",    callback_data=f"vc|stop|{cid}"),
            InlineKeyboardButton("📋 Queue",   callback_data=f"vc|queue|{cid}"),
        ],
    ])


def search_kb(results: list) -> InlineKeyboardMarkup:
    rows = []
    for i, r in enumerate(results):
        lbl = r["title"][:40] + "…" if len(r["title"]) > 40 else r["title"]
        rows.append([InlineKeyboardButton(
            f"🎵 {lbl}  [{fmt_dur(r['duration'])}]",
            callback_data=f"pick|{i}"
        )])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="pick|cancel")])
    return InlineKeyboardMarkup(rows)


async def do_play(cid: int, filepath: str, track: dict, msg: Message):
    """Stream audio file into the voice chat and update the message."""
    dur = fmt_dur(track["duration"])
    try:
        await calls.play(
            cid,
            MediaStream(
                filepath,
                audio_quality=AudioQuality.HIGH,
            ),
        )
        Q.set_current(cid, track)
        await msg.edit_text(
            f"🎵 **Now Playing**\n\n"
            f"**{track['title']}**\n"
            f"👤 {track['channel']}  ·  ⏱ {dur}\n\n"
            f"_Thrino Music Bot_ 🎧",
            reply_markup=player_kb(cid),
        )
    except NoActiveGroupCall:
        await msg.edit_text(
            "❌ **No active voice chat.**\n\n"
            "Start a Voice Chat in this group first:\n"
            "Group name → ··· → Start Voice Chat\n"
            "Then use `/play` again."
        )
    except AlreadyJoinedError:
        # Already in VC, change stream instead
        await calls.change_stream(
            cid,
            MediaStream(filepath, audio_quality=AudioQuality.HIGH),
        )
        Q.set_current(cid, track)
        await msg.edit_text(
            f"🎵 **Now Playing**\n\n"
            f"**{track['title']}**\n"
            f"👤 {track['channel']}  ·  ⏱ {dur}\n\n"
            f"_Thrino Music Bot_ 🎧",
            reply_markup=player_kb(cid),
        )
    except Exception as e:
        log.exception("do_play error")
        await msg.edit_text(f"❌ **Error joining voice chat:**\n`{e}`")


# ════════════════════════════════════════════════════════════
#   /start  /help
# ════════════════════════════════════════════════════════════

HELP = """
╔══════════════════════════════════════╗
║      🎵  T H R I N O  M U S I C     ║
║      Voice Chat DJ + Group Manager  ║
╚══════════════════════════════════════╝

**🎵 Music**
• `/play <song or URL>` — Play in VC
• `/vplay <YouTube URL>` — Play video in VC
• `/search <query>` — Pick from 5 results
• `/pause` — Pause ⏸
• `/resume` — Resume ▶️
• `/skip` — Skip ⏭
• `/stop` — Stop & leave ⏹
• `/loop` — Toggle loop 🔁
• `/queue` — Show queue 📋
• `/np` — Now playing 🎶
• `/volume <1-200>` — Set volume 🔊

**🛡️ Group Manager** _(admins only)_
• `/ban` · `/unban` · `/kick`
• `/mute` · `/unmute`
• `/promote` · `/demote`
• `/warn` · `/warns` · `/resetwarns`
• `/pin` · `/unpin`
• `/purge` — Delete messages in bulk
• `/setgrouptitle <title>`
• `/setwelcome <text>` — Set welcome msg
• `/stats` — Group stats

**ℹ️ Info**
• `/id` — Get your / replied user ID
• `/info @user` — User info
• `/ping` — Check bot latency
• `/cookies` — Cookie status (owner only)
"""


@bot.on_message(filters.command(["start", "help"]))
async def cmd_help(_, msg: Message):
    ck = "✅ Loaded" if os.path.isfile(Config.COOKIES_FILE) else "⚠️ Not loaded"
    await msg.reply_text(
        HELP + f"\n🍪 **Cookies:** {ck}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "➕ Add to Group",
                url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true"
            ),
            InlineKeyboardButton("📢 Support", url=Config.SUPPORT),
        ]]),
    )


# ════════════════════════════════════════════════════════════
#   /ping  /id  /info  /stats
# ════════════════════════════════════════════════════════════

@bot.on_message(filters.command("ping"))
async def cmd_ping(_, msg: Message):
    import time
    t = time.monotonic()
    m = await msg.reply("🏓 Pinging…")
    ms = round((time.monotonic() - t) * 1000)
    await m.edit_text(f"🏓 **Pong!** `{ms}ms`")


@bot.on_message(filters.command("id"))
async def cmd_id(_, msg: Message):
    if msg.reply_to_message:
        u = msg.reply_to_message.from_user
        await msg.reply(f"👤 **{u.first_name}**\nID: `{u.id}`")
    else:
        await msg.reply(f"👤 **Your ID:** `{msg.from_user.id}`\n💬 **Chat ID:** `{msg.chat.id}`")


@bot.on_message(filters.command("info"))
async def cmd_info(_, msg: Message):
    user_obj = await resolve_target(_, msg)
    if not user_obj:
        user_obj = msg.from_user
    mention = user_obj.mention
    await msg.reply(
        f"👤 **User Info**\n\n"
        f"**Name:** {user_obj.first_name} {user_obj.last_name or ''}\n"
        f"**Username:** @{user_obj.username or 'none'}\n"
        f"**ID:** `{user_obj.id}`\n"
        f"**DC:** {user_obj.dc_id or 'unknown'}"
    )


@bot.on_message(filters.command("stats") & filters.group)
async def cmd_stats(_, msg: Message):
    chat = msg.chat
    count = await bot.get_chat_members_count(chat.id)
    await msg.reply(
        f"📊 **Group Stats**\n\n"
        f"**Name:** {chat.title}\n"
        f"**ID:** `{chat.id}`\n"
        f"**Members:** {count:,}\n"
        f"**Type:** {chat.type.name.title()}"
    )


# ════════════════════════════════════════════════════════════
#   /cookies  (owner only)
# ════════════════════════════════════════════════════════════

@bot.on_message(filters.command("cookies"))
async def cmd_cookies(_, msg: Message):
    if msg.from_user.id != Config.OWNER_ID:
        return await msg.reply("🔒 Owner only.")
    cf = Config.COOKIES_FILE
    if os.path.isfile(cf):
        await msg.reply(
            f"🍪 **Cookies active**\n`{cf}`  ({os.path.getsize(cf):,} bytes)\n\n"
            "✅ All yt-dlp requests use these cookies."
        )
    else:
        await msg.reply(
            f"⚠️ **No cookies file at** `{cf}`\n\n"
            "**To get cookies:**\n"
            "1. Install **'Get cookies.txt LOCALLY'** in Chrome/Firefox\n"
            "2. Log into **youtube.com**\n"
            "3. Export → save as `cookies.txt` next to `bot.py`\n"
            "4. Restart the bot"
        )


# ════════════════════════════════════════════════════════════
#   /play
# ════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["play", "p"]) & filters.group)
async def cmd_play(_, msg: Message):
    cid = msg.chat.id
    if len(msg.command) < 2:
        return await msg.reply("🎵 Usage: `/play <song name or YouTube URL>`")

    query = " ".join(msg.command[1:])
    smsg  = await msg.reply("🔍 **Searching…**")

    is_url = bool(re.match(r"https?://", query))
    if is_url:
        track = get_info(query) or {"title": query[:60], "url": query, "duration": 0, "channel": "Direct URL"}
    else:
        track = search_one(query)

    if not track or not track.get("url"):
        return await smsg.edit_text("❌ **No results found.** Try a different search.")

    if Q.is_active(cid):
        Q.enqueue(cid, track)
        return await smsg.edit_text(
            f"📋 **Added to Queue #{Q.size(cid)}**\n\n"
            f"🎵 **{track['title']}**\n"
            f"👤 {track['channel']}  ·  ⏱ {fmt_dur(track['duration'])}"
        )

    await smsg.edit_text(f"⬇️ **Downloading…**\n`{track['title']}`")
    fp = download_audio(track["url"])
    if not fp:
        return await smsg.edit_text(
            "❌ **Download failed.**\n"
            "Try adding `cookies.txt` — run `/cookies` to check."
        )
    await do_play(cid, fp, track, smsg)


# ════════════════════════════════════════════════════════════
#   /vplay  (video → audio)
# ════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["vplay", "vp"]) & filters.group)
async def cmd_vplay(_, msg: Message):
    cid = msg.chat.id
    if len(msg.command) < 2:
        return await msg.reply("🎬 Usage: `/vplay <YouTube URL>`")

    url  = msg.command[1]
    if not re.match(r"https?://", url):
        return await msg.reply("❌ `/vplay` needs a direct URL.")

    smsg = await msg.reply("🔍 **Fetching video info…**")
    track = get_info(url)
    if not track:
        track = {"title": url[:60], "url": url, "duration": 0, "channel": "Direct URL"}

    if Q.is_active(cid):
        Q.enqueue(cid, track)
        return await smsg.edit_text(
            f"📋 **Added to Queue #{Q.size(cid)}** (video)\n\n"
            f"🎬 **{track['title']}**"
        )

    await smsg.edit_text(f"⬇️ **Downloading video audio…**\n`{track['title']}`")
    fp = download_audio(track["url"])
    if not fp:
        return await smsg.edit_text("❌ **Download failed.**")
    await do_play(cid, fp, track, smsg)


# ════════════════════════════════════════════════════════════
#   /search
# ════════════════════════════════════════════════════════════

@bot.on_message(filters.command("search") & filters.group)
async def cmd_search(_, msg: Message):
    if len(msg.command) < 2:
        return await msg.reply("🔍 Usage: `/search <song name>`")

    query   = " ".join(msg.command[1:])
    smsg    = await msg.reply("🔍 **Searching YouTube…**")
    results = search_many(query, 5)

    if not results:
        return await smsg.edit_text("❌ **No results found.**")

    Q.cache_search(msg.from_user.id, results)

    lines = "🔍 **Search Results:**\n\n"
    for i, r in enumerate(results, 1):
        lines += f"`{i}.` **{r['title'][:50]}**\n   ⏱ {fmt_dur(r['duration'])}  ·  👤 {r['channel']}\n\n"

    await smsg.edit_text(lines, reply_markup=search_kb(results))


# ════════════════════════════════════════════════════════════
#   Playback controls
# ════════════════════════════════════════════════════════════

@bot.on_message(filters.command("pause") & filters.group)
async def cmd_pause(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    try:
        await calls.pause_stream(msg.chat.id)
        await msg.reply("⏸ **Paused.**")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("resume") & filters.group)
async def cmd_resume(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    try:
        await calls.resume_stream(msg.chat.id)
        await msg.reply("▶️ **Resumed.**")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("skip") & filters.group)
async def cmd_skip(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    cid = msg.chat.id
    nxt = Q.next_track(cid)
    if not nxt:
        try:
            await calls.leave_group_call(cid)
        except Exception:
            pass
        Q.clear(cid)
        return await msg.reply("⏹ **Queue ended — left voice chat.**")

    smsg = await msg.reply(f"⬇️ Loading **{nxt['title']}**…")
    fp   = download_audio(nxt["url"])
    if not fp:
        return await smsg.edit_text("❌ **Download failed for next track.**")
    await do_play(cid, fp, nxt, smsg)


@bot.on_message(filters.command("stop") & filters.group)
async def cmd_stop(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    cid = msg.chat.id
    try:
        await calls.leave_group_call(cid)
    except Exception:
        pass
    Q.clear(cid)
    await msg.reply("⏹ **Stopped and left voice chat.**")


@bot.on_message(filters.command("loop") & filters.group)
async def cmd_loop(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    state = Q.toggle_loop(msg.chat.id)
    await msg.reply(f"🔁 **Loop {'enabled' if state else 'disabled'}.**")


@bot.on_message(filters.command("queue") & filters.group)
async def cmd_queue(_, msg: Message):
    cid = msg.chat.id
    cur = Q.get_current(cid)
    upc = Q.get_all(cid)
    if not cur and not upc:
        return await msg.reply("📋 **Queue is empty.**")
    txt = "📋 **Queue**\n\n"
    if cur:
        txt += f"🎵 **Now:** {cur['title']}\n\n"
    if upc:
        txt += "**Up next:**\n"
        for i, t in enumerate(upc[:10], 1):
            txt += f"`{i}.` {t['title'][:45]}\n"
        if len(upc) > 10:
            txt += f"\n_…and {len(upc)-10} more_"
    await msg.reply(txt)


@bot.on_message(filters.command("np") & filters.group)
async def cmd_np(_, msg: Message):
    cur = Q.get_current(msg.chat.id)
    if not cur:
        return await msg.reply("🔇 **Nothing is playing.**")
    await msg.reply(
        f"🎶 **Now Playing**\n\n**{cur['title']}**\n"
        f"👤 {cur['channel']}  ·  ⏱ {fmt_dur(cur['duration'])}\n"
        f"🔁 Loop: {'on' if Q.is_loop(msg.chat.id) else 'off'}",
        reply_markup=player_kb(msg.chat.id),
    )


@bot.on_message(filters.command("volume") & filters.group)
async def cmd_volume(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    if len(msg.command) < 2:
        vol = Q.get_volume(msg.chat.id)
        return await msg.reply(f"🔊 **Current volume:** {vol}%\nUsage: `/volume <1-200>`")
    try:
        vol = max(1, min(200, int(msg.command[1])))
        await calls.change_volume_call(msg.chat.id, vol)
        Q.set_volume(msg.chat.id, vol)
        await msg.reply(f"🔊 **Volume set to {vol}%**")
    except ValueError:
        await msg.reply("❌ Provide a number between 1 and 200.")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


# ════════════════════════════════════════════════════════════
#   🛡️  GROUP MANAGER
# ════════════════════════════════════════════════════════════

_warns: dict[str, int]    = {}
_welcome: dict[int, str]  = {}


@bot.on_message(filters.command("ban") & filters.group)
async def cmd_ban(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    reason = " ".join(msg.command[2:]) if len(msg.command) > 2 else "No reason"
    try:
        await bot.ban_chat_member(msg.chat.id, tgt.id)
        await msg.reply(f"🔨 **Banned** {tgt.mention}\n📝 Reason: {reason}")
    except ChatAdminRequired:
        await msg.reply("❌ I need Ban permission.")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("unban") & filters.group)
async def cmd_unban(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    try:
        await bot.unban_chat_member(msg.chat.id, tgt.id)
        await msg.reply(f"✅ **Unbanned** {tgt.mention}")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("kick") & filters.group)
async def cmd_kick(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    try:
        await bot.ban_chat_member(msg.chat.id, tgt.id)
        await bot.unban_chat_member(msg.chat.id, tgt.id)
        await msg.reply(f"👢 **Kicked** {tgt.mention}")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("mute") & filters.group)
async def cmd_mute(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    try:
        await bot.restrict_chat_member(msg.chat.id, tgt.id, ChatPermissions())
        await msg.reply(f"🔇 **Muted** {tgt.mention}")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("unmute") & filters.group)
async def cmd_unmute(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    try:
        await bot.restrict_chat_member(
            msg.chat.id, tgt.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        await msg.reply(f"🔊 **Unmuted** {tgt.mention}")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("promote") & filters.group)
async def cmd_promote(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    try:
        await bot.promote_chat_member(
            msg.chat.id, tgt.id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=True,
            can_invite_users=True,
            can_pin_messages=True,
        )
        await msg.reply(f"⭐ **Promoted** {tgt.mention}")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("demote") & filters.group)
async def cmd_demote(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    try:
        await bot.promote_chat_member(
            msg.chat.id, tgt.id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
        await msg.reply(f"⬇️ **Demoted** {tgt.mention}")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("pin") & filters.group)
async def cmd_pin(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    if not msg.reply_to_message:
        return await msg.reply("❓ Reply to the message to pin.")
    try:
        await bot.pin_chat_message(msg.chat.id, msg.reply_to_message.id, disable_notification=False)
        await msg.reply("📌 **Pinned.**")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("unpin") & filters.group)
async def cmd_unpin(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    try:
        await bot.unpin_chat_message(msg.chat.id)
        await msg.reply("📌 **Unpinned.**")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


@bot.on_message(filters.command("purge") & filters.group)
async def cmd_purge(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    if not msg.reply_to_message:
        return await msg.reply("❓ Reply to the first message to purge from.")
    start  = msg.reply_to_message.id
    end    = msg.id
    ids    = list(range(start, end + 1))
    deleted = 0
    for i in range(0, len(ids), 100):
        try:
            await bot.delete_messages(msg.chat.id, ids[i:i+100])
            deleted += min(100, len(ids) - i)
        except Exception:
            pass
    n = await msg.reply(f"🗑️ **Purged {deleted} messages.**")
    await asyncio.sleep(4)
    try:
        await n.delete()
    except Exception:
        pass


# ── Warn system ──────────────────────────────────────────────

@bot.on_message(filters.command("warn") & filters.group)
async def cmd_warn(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    key    = f"{msg.chat.id}:{tgt.id}"
    _warns[key] = _warns.get(key, 0) + 1
    count  = _warns[key]
    reason = " ".join(msg.command[2:]) if len(msg.command) > 2 else "No reason given"
    await msg.reply(
        f"⚠️ {tgt.mention} warned  ({count}/{Config.MAX_WARNS})\n"
        f"📝 **Reason:** {reason}"
    )
    if count >= Config.MAX_WARNS:
        try:
            await bot.ban_chat_member(msg.chat.id, tgt.id)
            await msg.reply(f"🔨 {tgt.mention} **auto-banned** after {Config.MAX_WARNS} warnings.")
            del _warns[key]
        except Exception as e:
            await msg.reply(f"❌ Auto-ban failed: `{e}`")


@bot.on_message(filters.command("warns") & filters.group)
async def cmd_warns(_, msg: Message):
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    key   = f"{msg.chat.id}:{tgt.id}"
    count = _warns.get(key, 0)
    await msg.reply(f"⚠️ {tgt.mention} has **{count}/{Config.MAX_WARNS}** warnings.")


@bot.on_message(filters.command("resetwarns") & filters.group)
async def cmd_resetwarns(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    tgt = await resolve_target(_, msg)
    if not tgt:
        return await msg.reply("❓ Reply to a user or provide @username.")
    _warns.pop(f"{msg.chat.id}:{tgt.id}", None)
    await msg.reply(f"✅ **Warnings reset** for {tgt.mention}.")


@bot.on_message(filters.command("setgrouptitle") & filters.group)
async def cmd_settitle(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    if len(msg.command) < 2:
        return await msg.reply("Usage: `/setgrouptitle <new title>`")
    title = " ".join(msg.command[1:])
    try:
        await bot.set_chat_title(msg.chat.id, title)
        await msg.reply(f"✅ **Title changed to:** {title}")
    except Exception as e:
        await msg.reply(f"❌ `{e}`")


# ── Welcome message system ───────────────────────────────────

@bot.on_message(filters.command("setwelcome") & filters.group)
async def cmd_setwelcome(_, msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.reply("🔒 Admins only.")
    if len(msg.command) < 2:
        return await msg.reply("Usage: `/setwelcome <message text>`\nUse {name} for the user's name.")
    text = " ".join(msg.command[1:])
    _welcome[msg.chat.id] = text
    await msg.reply(f"✅ **Welcome message set:**\n\n{text}")


@bot.on_message(filters.new_chat_members)
async def on_new_member(_, msg: Message):
    cid = msg.chat.id
    if cid not in _welcome:
        return
    tmpl = _welcome[cid]
    for member in msg.new_chat_members:
        text = tmpl.replace("{name}", member.mention)
        await msg.reply(text)


# ════════════════════════════════════════════════════════════
#   CALLBACK QUERY HANDLER
# ════════════════════════════════════════════════════════════

@bot.on_callback_query()
async def cb(_, cb_q: CallbackQuery):
    data = cb_q.data
    cid  = cb_q.message.chat.id
    uid  = cb_q.from_user.id

    # ── Search pick ───────────────────────────────────────────
    if data.startswith("pick|"):
        val = data.split("|", 1)[1]
        if val == "cancel":
            return await cb_q.message.delete()

        idx     = int(val)
        results = Q.get_search(uid)
        if not results or idx >= len(results):
            return await cb_q.answer("❌ Search expired.", show_alert=True)

        track = results[idx]
        await cb_q.message.edit_text(f"⬇️ **Downloading…**\n`{track['title']}`")
        fp = download_audio(track["url"])
        if not fp:
            return await cb_q.message.edit_text("❌ Download failed.")

        if Q.is_active(cid):
            Q.enqueue(cid, track)
            await cb_q.message.edit_text(
                f"📋 **Added to Queue #{Q.size(cid)}**\n\n🎵 **{track['title']}**"
            )
        else:
            await do_play(cid, fp, track, cb_q.message)
        return

    # ── Voice chat controls ───────────────────────────────────
    if data.startswith("vc|"):
        _, action, raw_cid = data.split("|")
        tcid = int(raw_cid)

        if not await is_admin(cid, uid):
            return await cb_q.answer("🔒 Admins only.", show_alert=True)

        if action == "pause":
            await calls.pause_stream(tcid)
            await cb_q.answer("⏸ Paused")

        elif action == "resume":
            await calls.resume_stream(tcid)
            await cb_q.answer("▶️ Resumed")

        elif action == "skip":
            nxt = Q.next_track(tcid)
            if not nxt:
                try:
                    await calls.leave_group_call(tcid)
                except Exception:
                    pass
                Q.clear(tcid)
                return await cb_q.answer("⏹ Queue ended", show_alert=True)
            fp = download_audio(nxt["url"])
            if fp:
                await calls.change_stream(tcid, MediaStream(fp, audio_quality=AudioQuality.HIGH))
                Q.set_current(tcid, nxt)
            await cb_q.answer(f"⏭ {nxt['title'][:30]}")

        elif action == "stop":
            try:
                await calls.leave_group_call(tcid)
            except Exception:
                pass
            Q.clear(tcid)
            await cb_q.answer("⏹ Stopped", show_alert=True)

        elif action == "loop":
            state = Q.toggle_loop(tcid)
            await cb_q.answer(f"🔁 Loop {'on' if state else 'off'}")
            # Refresh the keyboard
            cur = Q.get_current(tcid)
            if cur:
                try:
                    await cb_q.message.edit_reply_markup(player_kb(tcid))
                except Exception:
                    pass

        elif action == "vdn":
            vol = max(1, Q.get_volume(tcid) - 10)
            await calls.change_volume_call(tcid, vol)
            Q.set_volume(tcid, vol)
            await cb_q.answer(f"🔉 Volume: {vol}%")
            try:
                await cb_q.message.edit_reply_markup(player_kb(tcid))
            except Exception:
                pass

        elif action == "vup":
            vol = min(200, Q.get_volume(tcid) + 10)
            await calls.change_volume_call(tcid, vol)
            Q.set_volume(tcid, vol)
            await cb_q.answer(f"🔊 Volume: {vol}%")
            try:
                await cb_q.message.edit_reply_markup(player_kb(tcid))
            except Exception:
                pass

        elif action == "vol":
            await cb_q.answer(f"🔊 Current: {Q.get_volume(tcid)}%", show_alert=True)

        elif action == "queue":
            cur = Q.get_current(tcid)
            upc = Q.get_all(tcid)
            txt = f"🎵 {cur['title'][:35]}\n" if cur else "Nothing playing.\n"
            for i, t in enumerate(upc[:5], 1):
                txt += f"{i}. {t['title'][:35]}\n"
            if not txt.strip():
                txt = "Queue is empty."
            await cb_q.answer(txt, show_alert=True)


# ════════════════════════════════════════════════════════════
#   STREAM END → auto-play next
# ════════════════════════════════════════════════════════════

@calls.on_stream_end()
async def on_stream_end(_, update):
    cid = update.chat_id
    nxt = Q.next_track(cid)
    if nxt:
        fp = download_audio(nxt["url"])
        if fp:
            try:
                await calls.change_stream(cid, MediaStream(fp, audio_quality=AudioQuality.HIGH))
                Q.set_current(cid, nxt)
                await bot.send_message(
                    cid,
                    f"⏭ **Auto-playing next:**\n🎵 **{nxt['title']}**",
                    reply_markup=player_kb(cid),
                )
            except Exception as e:
                log.error(f"auto-play error: {e}")
    else:
        Q.clear(cid)
        try:
            await calls.leave_group_call(cid)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
#   STARTUP
# ════════════════════════════════════════════════════════════

async def main():
    log.info("══════════════════════════════════════════")
    log.info("  🎵  Thrino Music Bot  —  Starting up")
    log.info("══════════════════════════════════════════")

    # Validate critical config
    if not Config.API_ID or not Config.API_HASH:
        log.critical("API_ID / API_HASH not set — check your env vars!")
        return
    if not Config.BOT_TOKEN:
        log.critical("BOT_TOKEN not set — check your env vars!")
        return
    if not Config.STRING_SESSION:
        log.critical(
            "STRING_SESSION not set!\n"
            "Run  python generate_session.py  to generate one.\n"
            "This is required — bot accounts cannot join voice chats."
        )
        return

    cf = Config.COOKIES_FILE
    log.info(f"  🍪  Cookies: {'loaded — ' + cf if os.path.isfile(cf) else 'not found (will work without)'}")

    await bot.start()
    me_bot = await bot.get_me()
    log.info(f"  🤖  Bot online: @{me_bot.username}")

    await user.start()
    me_user = await user.get_me()
    log.info(f"  👤  Userbot online: @{me_user.username or me_user.first_name}")

    await calls.start()
    log.info("  📡  PyTgCalls ready")
    log.info("══════════════════════════════════════════")

    await idle()


if __name__ == "__main__":
    asyncio.run(main())
