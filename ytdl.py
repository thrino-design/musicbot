import os
import logging
from typing import Optional
from yt_dlp import YoutubeDL
from config import Config

log = logging.getLogger("thrino.ytdl")

# ════════════════════════════════════════════════════════════
#   🎵 THRINO MUSIC BOT  ·  ytdl.py
#   All yt-dlp calls go here so cookies are always injected.
# ════════════════════════════════════════════════════════════

def _opts(**extra) -> dict:
    base = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        **extra,
    }
    cf = Config.COOKIES_FILE
    if cf and os.path.isfile(cf):
        base["cookiefile"] = cf
    return base


def search_one(query: str) -> Optional[dict]:
    """Return top YouTube result for query."""
    try:
        with YoutubeDL(_opts(skip_download=True)) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if info and info.get("entries"):
                return _fmt(info["entries"][0])
    except Exception as e:
        log.error(f"search_one: {e}")
    return None


def search_many(query: str, n: int = 5) -> list:
    """Return up to n YouTube results."""
    try:
        with YoutubeDL(_opts(skip_download=True)) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
            if info and info.get("entries"):
                return [_fmt(e) for e in info["entries"] if e][:n]
    except Exception as e:
        log.error(f"search_many: {e}")
    return []


def get_info(url: str) -> Optional[dict]:
    """Fetch metadata for a direct URL without downloading."""
    try:
        with YoutubeDL(_opts(skip_download=True)) as ydl:
            info = ydl.extract_info(url, download=False)
            return _fmt(info)
    except Exception as e:
        log.error(f"get_info: {e}")
    return None


def download_audio(url: str) -> Optional[str]:
    """Download best audio, convert to mp3, return file path."""
    os.makedirs(Config.DL_DIR, exist_ok=True)
    opts = _opts(
        format="bestaudio/best",
        outtmpl=f"{Config.DL_DIR}/%(id)s.%(ext)s",
        postprocessors=[{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    )
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            if os.path.isfile(path):
                return path
            log.error(f"Expected file not found: {path}")
    except Exception as e:
        log.error(f"download_audio: {e}")
    return None


def _fmt(e: dict) -> dict:
    return {
        "title":    e.get("title", "Unknown"),
        "url":      e.get("webpage_url") or e.get("url", ""),
        "duration": int(e.get("duration") or 0),
        "channel":  e.get("channel") or e.get("uploader") or "Unknown",
        "thumb":    e.get("thumbnail", ""),
    }


def fmt_dur(sec: int) -> str:
    sec = int(sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
