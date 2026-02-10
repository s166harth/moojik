import threading
from dataclasses import dataclass
from typing import List, Optional

# --- Data Structure ---
@dataclass
class QueueItem:
    url: str
    title: str
    ip: str
    username: str
    added_at: str
    processed_at: Optional[str] = None


# Shared State protected by a lock
queue_lock = threading.RLock()
music_playlist: List[QueueItem] = []
played_history: List[QueueItem] = []
rejected_history: List[QueueItem] = []
current_video_id: Optional[str] = None
player_opened: bool = False

AVERAGE_SONG_DURATION_MIN = 4
