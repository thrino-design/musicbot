# 🎵 THRINO MUSIC BOT — Complete Setup Guide

```
╔══════════════════════════════════════════════════════════════╗
║           🎵  T H R I N O   M U S I C   B O T               ║
║          Voice Chat  +  Group Manager  +  More               ║
╚══════════════════════════════════════════════════════════════╝
```

---

## ⚠️ THE MOST IMPORTANT THING TO UNDERSTAND

**Why previous bots never worked in voice chat:**

Telegram bots (created via @BotFather) **CANNOT join voice chats**.
This is a Telegram rule — not a code problem.

To stream music into a voice chat, you need **two accounts**:

| Account | What it does |
|---------|-------------|
| **Bot account** (from @BotFather) | Handles commands like `/play`, `/ban` |
| **User account** (your secondary Telegram account) | Actually joins the voice chat and streams music |

The user account is called a **"userbot"** or **"assistant"**. It logs in via a **Pyrogram String Session** (not a bot token).

---

## 📁 Files

```
thrino-music-bot/
├── bot.py                ← Main code (everything)
├── config.py             ← Reads env vars
├── queue_manager.py      ← Song queue logic
├── ytdl.py               ← YouTube download + search
├── generate_session.py   ← Run this ONCE to get STRING_SESSION
├── requirements.txt      ← Dependencies
├── render.yaml           ← Render.com deploy config
├── .env.example          ← Template for credentials
├── .gitignore
├── cookies.txt           ← YOU provide this (YouTube cookies)
└── INSTRUCTIONS.md       ← This file
```

---

## 🔑 STEP 1 — Get Credentials (do this first)

### A) API ID + API Hash
1. Go to **https://my.telegram.org/apps**
2. Log in with your phone number
3. Click **Create Application**
4. Copy `app_id` (number) and `app_hash` (32-char string)

### B) Bot Token
1. Open Telegram → **@BotFather**
2. `/newbot` → follow prompts
3. Copy the token: `123456789:AABBxxxxxxx`

### C) String Session (CRITICAL — without this voice chat won't work)

You need a **secondary Telegram account** for this.
Do NOT use your main personal account.

**On your local machine or Termux:**
```bash
pip install pyrogram TgCrypto
python generate_session.py
```

It will ask for `API_ID`, `API_HASH`, and a phone number.
Enter the phone number of your **secondary account**.
It will send you a verification code on Telegram.
After entering the code it prints a long string — **copy it**.
That is your `STRING_SESSION`.

> Keep it secret. It gives full access to that Telegram account.

### D) Your Owner ID
1. Open Telegram → **@userinfobot**
2. Send `/start`
3. Copy the **Id** number

---

## 🍪 STEP 2 — YouTube Cookies (recommended)

Without cookies, YouTube often blocks downloads on cloud servers.

1. Install **"Get cookies.txt LOCALLY"** extension in Chrome or Firefox
2. Open **https://youtube.com** while logged in to your Google account
3. Click the extension icon → **Export** → save as `cookies.txt`
4. Place `cookies.txt` in the same folder as `bot.py`

---

## 🚀 STEP 3 — Deploy on Render.com

### 3.1 Push to GitHub

```bash
git init
git add .
git commit -m "Thrino Music Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/thrino-music-bot.git
git push -u origin main
```

> Remove `cookies.txt` from `.gitignore` first if you want to include it,
> or use Render's **Secret Files** feature (see 3.3).

### 3.2 Create Render Service

1. Go to **https://render.com** → sign in
2. Click **New +** → **Background Worker**
   ⚠️ Must be **Background Worker**, NOT Web Service
3. Connect your GitHub repo
4. Render auto-reads `render.yaml`

### 3.3 Add Environment Variables

In Render dashboard → your service → **Environment** tab:

| Variable | Value |
|----------|-------|
| `API_ID` | Your number from my.telegram.org |
| `API_HASH` | Your hash from my.telegram.org |
| `BOT_TOKEN` | Token from @BotFather |
| `STRING_SESSION` | Long string from generate_session.py |
| `OWNER_ID` | Your Telegram user ID |
| `BOT_USERNAME` | `ThrinoMusicBot` (no @) |
| `COOKIES_FILE` | `cookies.txt` |

**For cookies.txt on Render (secret file method):**
- Go to your service → **Secret Files** tab
- Add path: `/opt/render/project/src/cookies.txt`
- Paste the contents of your cookies.txt
- Set env var `COOKIES_FILE` = `/opt/render/project/src/cookies.txt`

### 3.4 Deploy

Click **Save Changes** → Render redeploys automatically.

Watch the **Logs** tab. You should see:
```
🤖  Bot online: @ThrinoMusicBot
👤  Userbot online: @YourAssistantAccount
📡  PyTgCalls ready
```

If you see an error about `STRING_SESSION` — re-run `generate_session.py`.

---

## ✅ STEP 4 — Set Up Your Group

1. **Add your bot** (@ThrinoMusicBot) to the group as **admin** with:
   - Delete messages
   - Ban users
   - Manage video chats
   - Restrict members
   - Pin messages

2. **Add your assistant account** (the secondary user account) to the group as **admin** with:
   - Manage video chats (required to join voice chat)

3. **Start a Voice Chat** in the group:
   - Tap group name at top → `···` → **Start Voice Chat**

4. Send `/play despacito` — should work!

---

## 🎵 All Commands

### Music
| Command | What it does |
|---------|-------------|
| `/play <song or URL>` | Search and play audio in voice chat |
| `/vplay <YouTube URL>` | Play video's audio in voice chat |
| `/search <query>` | Search YouTube, pick from 5 results |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/skip` | Skip to next queued song |
| `/stop` | Stop music and leave voice chat |
| `/loop` | Toggle loop mode |
| `/queue` | Show current queue |
| `/np` | Now playing info + player controls |
| `/volume <1-200>` | Set volume |

### Info
| Command | What it does |
|---------|-------------|
| `/ping` | Bot latency |
| `/id` | Your/replied user ID |
| `/info @user` | User info |
| `/stats` | Group stats |

### Group Management (admins only)
| Command | What it does |
|---------|-------------|
| `/ban @user [reason]` | Ban a user |
| `/unban @user` | Unban a user |
| `/kick @user` | Kick a user |
| `/mute @user` | Mute a user |
| `/unmute @user` | Unmute a user |
| `/promote @user` | Promote to admin |
| `/demote @user` | Remove admin rights |
| `/pin` | Pin replied message |
| `/unpin` | Unpin current message |
| `/purge` | Delete messages from reply to now |
| `/warn @user [reason]` | Warn (auto-ban at 3) |
| `/warns @user` | Check warning count |
| `/resetwarns @user` | Reset warnings |
| `/setgrouptitle <title>` | Change group title |
| `/setwelcome <text>` | Set welcome message |

### Owner only
| Command | What it does |
|---------|-------------|
| `/cookies` | Check YouTube cookie status |

---

## 🛠️ Troubleshooting

### ❌ "No active voice chat"
Start a voice chat in the group first.
Tap group name → `···` → Start Voice Chat.

### ❌ Bot doesn't respond at all
- Check Render logs for startup errors
- Verify `BOT_TOKEN` is correct — no spaces, no quotes
- Make sure the bot is admin in the group

### ❌ "STRING_SESSION not set" in logs
Run `python generate_session.py` again and copy the output.

### ❌ Music downloads but doesn't play
Your assistant account might not be admin with **Manage Video Chats** permission.
Also check it is in the group.

### ❌ Download failed
YouTube is blocking requests. Add `cookies.txt` — use `/cookies` to verify.
Also run: `pip install -U yt-dlp` (yt-dlp updates frequently).

### ❌ Works locally but not on Render
- Render needs `ffmpeg` — `render.yaml` installs it automatically
- Check that all 6 env vars are set in the Render dashboard

---

## 🔄 Updating

```bash
git add .
git commit -m "update"
git push
```
Render auto-redeploys on every push.

---

_Thrino Music Bot — smooth voice chat sessions_ 🎧
