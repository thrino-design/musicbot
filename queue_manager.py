from typing import Optional

# ════════════════════════════════════════════════════════════
#   🎵 THRINO MUSIC BOT  ·  queue_manager.py
# ════════════════════════════════════════════════════════════

class QueueManager:
    def __init__(self):
        self._current:  dict[int, dict] = {}   # cid → track
        self._queue:    dict[int, list] = {}   # cid → [track, ...]
        self._search:   dict[int, list] = {}   # uid → last search results
        self._loop:     dict[int, bool] = {}   # cid → loop flag
        self._volume:   dict[int, int]  = {}   # cid → volume 0-200

    # ── current ──────────────────────────────────────────────

    def set_current(self, cid: int, track: dict):
        self._current[cid] = track

    def get_current(self, cid: int) -> Optional[dict]:
        return self._current.get(cid)

    def is_active(self, cid: int) -> bool:
        return cid in self._current and bool(self._current[cid])

    # ── queue ────────────────────────────────────────────────

    def enqueue(self, cid: int, track: dict):
        self._queue.setdefault(cid, []).append(track)

    def get_all(self, cid: int) -> list:
        return list(self._queue.get(cid, []))

    def size(self, cid: int) -> int:
        return len(self._queue.get(cid, []))

    def next_track(self, cid: int) -> Optional[dict]:
        q = self._queue.get(cid, [])
        if q:
            track = q.pop(0)
            # If loop is on, re-add current to end
            if self._loop.get(cid) and self._current.get(cid):
                q.append(self._current[cid])
            self._current[cid] = track
            return track
        self._current.pop(cid, None)
        return None

    def clear(self, cid: int):
        self._queue.pop(cid, None)
        self._current.pop(cid, None)
        self._loop.pop(cid, None)

    # ── loop ─────────────────────────────────────────────────

    def toggle_loop(self, cid: int) -> bool:
        """Toggle loop mode, return new state."""
        state = not self._loop.get(cid, False)
        self._loop[cid] = state
        return state

    def is_loop(self, cid: int) -> bool:
        return self._loop.get(cid, False)

    # ── volume ───────────────────────────────────────────────

    def set_volume(self, cid: int, vol: int):
        self._volume[cid] = max(1, min(200, vol))

    def get_volume(self, cid: int) -> int:
        return self._volume.get(cid, 100)

    # ── search cache ─────────────────────────────────────────

    def cache_search(self, uid: int, results: list):
        self._search[uid] = results

    def get_search(self, uid: int) -> Optional[list]:
        return self._search.get(uid)


# Singleton
Q = QueueManager()
