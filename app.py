import json
import threading
import webbrowser
import queue
import re
import datetime
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import List, Optional
from flask import (
    Flask,
    request,
    render_template_string,
    flash,
    redirect,
    url_for,
    jsonify,
)
from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Label,
    Button,
    Input,
    TabbedContent,
    TabPane,
)
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual import work


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

# --- Flask Web Server ---
flask_app = Flask(__name__)
flask_app.secret_key = "supersecretkey"

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Queue Submission</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #f4f4f9; color: #333; }
        .container { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { margin-top: 0; color: #2c3e50; text-align: center; }
        
        .form-group { margin-bottom: 1rem; }
        input[type="text"] { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; box-sizing: border-box; font-size: 1rem; transition: border-color 0.3s; margin-top: 5px;}
        input[type="text"]:focus { border-color: #3498db; outline: none; }
        label { font-weight: bold; color: #555; }
        
        button { width: 100%; background: #3498db; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-size: 1.1rem; font-weight: bold; transition: background 0.3s; margin-top: 10px; }
        button:hover { background: #2980b9; }
        
        .message { padding: 12px; margin-bottom: 1.5rem; border-radius: 8px; text-align: center; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        
        .section { margin-top: 3rem; }
        h2 { border-bottom: 2px solid #eee; padding-bottom: 0.5rem; margin-bottom: 1rem; color: #444; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; }
        th { background-color: #f8f9fa; font-weight: 600; color: #555; }
        tr:hover { background-color: #f1f1f1; }
        .empty-msg { text-align: center; color: #888; padding: 1.5rem; font-style: italic; }
        .wait-time { font-weight: bold; color: #e67e22; }
        .user-tag { background: #e8f4f8; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: #2980b9; }
        .nav-link { display: block; text-align: center; margin-bottom: 1rem; color: #3498db; text-decoration: none; }
        .nav-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/player" target="_blank" class="nav-link">Open Player Window</a>
        <h1>Add Music to Queue</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="message {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="post">
            <div class="form-group">
                <label for="username">Your Name:</label>
                <input type="text" id="username" name="username" placeholder="Enter your name" required>
            </div>
            <div class="form-group">
                <label for="url">YouTube URL:</label>
                <input type="text" id="url" name="url" placeholder="Paste YouTube URL here..." required>
            </div>
            <button type="submit">Add to Queue</button>
        </form>

        <div class="section">
            <h2>Current Queue</h2>
            {% if playlist %}
                <table>
                    <thead>
                        <tr>
                            <th style="width: 5%;">#</th>
                            <th style="width: 35%;">Title</th>
                            <th style="width: 15%;">User</th>
                            <th style="width: 25%;">Link</th>
                            <th style="width: 20%;">Est. Wait</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in playlist %}
                        <tr>
                            <td>{{ loop.index }}</td>
                            <td>{{ item.title }}</td>
                            <td><span class="user-tag">{{ item.username }}</span></td>
                            <td><a href="{{ item.url }}" target="_blank">Watch</a></td>
                            <td class="wait-time">{{ (loop.index0 * avg_duration) }} mins</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% else %}
                <div class="empty-msg">The queue is currently empty.</div>
            {% endif %}
        </div>
        
        <div class="section">
             <h2>Recently Played</h2>
             {% if played %}
                <table>
                    <thead>
                        <tr>
                            <th>Title</th>
                            <th>User</th>
                            <th>Played At</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in played|reverse %}
                        <tr>
                            <td>{{ item.title }}</td>
                            <td>{{ item.username }}</td>
                            <td>{{ item.processed_at }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% else %}
                 <div class="empty-msg">No songs played yet.</div>
            {% endif %}
        </div>
        
        <div class="section">
             <h2>Rejected Requests</h2>
             {% if rejected %}
                <table>
                    <thead>
                        <tr>
                            <th>Title</th>
                            <th>User</th>
                            <th>Rejected At</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in rejected|reverse %}
                        <tr>
                            <td>{{ item.title }}</td>
                            <td>{{ item.username }}</td>
                            <td>{{ item.processed_at }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% else %}
                 <div class="empty-msg">No rejected requests.</div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

PLAYER_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Moojik Player</title>
    <style>
        body { background: #000; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: sans-serif; }
        #player-container { width: 80%; height: 80%; display: flex; justify-content: center; align-items: center; background: #222; border-radius: 10px; }
        iframe { width: 100%; height: 100%; border: none; border-radius: 10px; }
        .status { margin-top: 20px; font-size: 1.2em; color: #888; }
    </style>
</head>
<body>
    <div id="player-container">
        <div class="status">Waiting for music...</div>
    </div>
    
    <script>
        let currentVideoId = null;
        
        function pollForUpdates() {
            fetch('/api/current')
                .then(response => response.json())
                .then(data => {
                    if (data.video_id && data.video_id !== currentVideoId) {
                        currentVideoId = data.video_id;
                        updatePlayer(currentVideoId);
                    }
                })
                .catch(err => console.error("Error polling:", err));
        }
        
        function updatePlayer(videoId) {
            const container = document.getElementById('player-container');
            container.innerHTML = `<iframe src="https://www.youtube.com/embed/${videoId}?autoplay=1" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
        }
        
        // Poll every 2 seconds
        setInterval(pollForUpdates, 2000);
    </script>
</body>
</html>
"""


def is_valid_youtube_url(url):
    youtube_regex = (
        r"(https?://)?(www\.)?"
        r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
        r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    )
    return re.match(youtube_regex, url) is not None


def get_youtube_title(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            meta_title = soup.find("meta", property="og:title")
            if meta_title:
                return str(meta_title["content"])
            if soup.title and soup.title.string:
                return str(soup.title.string).replace(" - YouTube", "")
    except Exception as e:
        print(f"Error fetching title: {e}")
    return "Unknown Title"


@flask_app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        username = request.form.get("username", "Anonymous").strip()
        user_ip = request.remote_addr or "Unknown"

        if not url:
            flash("Please enter a URL.", "error")
        elif is_valid_youtube_url(url):
            title = get_youtube_title(url)

            with queue_lock:
                item = QueueItem(
                    url=url,
                    title=title,
                    ip=str(user_ip),
                    username=username,
                    added_at=datetime.datetime.now().strftime("%H:%M:%S"),
                )
                music_playlist.append(item)
            flash(f"Successfully added '{title}'!", "success")
        else:
            flash("Invalid YouTube URL.", "error")
        return redirect(url_for("index"))

    with queue_lock:
        return render_template_string(
            HTML_TEMPLATE,
            playlist=list(music_playlist),
            played=list(played_history),
            rejected=list(rejected_history),
            avg_duration=AVERAGE_SONG_DURATION_MIN,
        )


def extract_video_id(url):
    """Extracts the video ID from a YouTube URL."""
    youtube_regex = (
        r"(https?://)?(www\.)?"
        r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
        r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    )
    match = re.match(youtube_regex, url)
    if match:
        return match.group(6)
    return None


@flask_app.route("/player")
def player():
    return render_template_string(PLAYER_TEMPLATE)


@flask_app.route("/api/current")
def current_song():
    with queue_lock:
        return jsonify({"video_id": current_video_id})


def run_flask():
    import socket
    from zeroconf import ServiceInfo, Zeroconf

    zeroconf = None
    info = None
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) # Connect to an external host to get local IP
        ip_address = s.getsockname()[0]
        s.close()

        desc = {'path': '/'}
        info = ServiceInfo(
            "_http._tcp.local.",
            "Moojik Queue._http._tcp.local.",
            addresses=[socket.inet_aton(ip_address)],
            port=5000,
            properties=desc,
            server="moojik.local.",
        )
        zeroconf = Zeroconf()
        zeroconf.register_service(info)
        print(f"mDNS service registered: http://moojik.local:5000 (or http://{ip_address}:5000)")

        flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    finally:
        if zeroconf:
            print("Unregistering mDNS service...")
            zeroconf.unregister_service(info)
            zeroconf.close()


# --- Textual TUI App ---
class MusicQueueApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    Header {
        dock: top;
    }
    Footer {
        dock: bottom;
    }
    DataTable {
        height: 1fr;
        border: solid green;
    }
    #input-container {
        height: auto;
        dock: bottom;
        padding: 1;
        border-top: solid blue;
    }
    TabbedContent {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "delete_item", "Reject Selected"),
        ("space", "play_item", "Play Selected"),
        ("e", "export_playlist", "Export Played"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("Queue Management (SPACE to Play, D to Reject):", classes="box")

        with TabbedContent(initial="tab-queue"):
            with TabPane("Queue", id="tab-queue"):
                yield DataTable(id="queue-table")
            with TabPane("Played History", id="tab-played"):
                yield DataTable(id="played-table")
            with TabPane("Rejected History", id="tab-rejected"):
                yield DataTable(id="rejected-table")

        with Container(id="input-container"):
            yield Label("Add Local URL:")
            yield Input(placeholder="Paste YouTube URL here...", id="url-input")
            yield Button("Add", id="add-btn", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        self.title = "Music Queue Manager"

        # Setup Queue Table
        q_table = self.query_one("#queue-table", DataTable)
        q_table.cursor_type = "row"
        q_table.add_columns(
            "Idx", "Title", "User", "IP", "URL", "Est. Wait", "Added At"
        )

        # Setup Played Table
        p_table = self.query_one("#played-table", DataTable)
        p_table.cursor_type = "row"
        p_table.add_columns("Title", "User", "URL", "Played At")

        # Setup Rejected Table
        r_table = self.query_one("#rejected-table", DataTable)
        r_table.cursor_type = "row"
        r_table.add_columns("Title", "User", "URL", "Rejected At")

        self.set_interval(1.0, self.refresh_tables)
        self.refresh_tables()

    def refresh_tables(self) -> None:
        with queue_lock:
            # Refresh Queue
            q_table = self.query_one("#queue-table", DataTable)
            self._update_table(q_table, music_playlist, "queue")

            # Refresh Played (Reverse order to show newest first)
            p_table = self.query_one("#played-table", DataTable)
            self._update_table(p_table, list(reversed(played_history)), "history")

            # Refresh Rejected
            r_table = self.query_one("#rejected-table", DataTable)
            self._update_table(r_table, list(reversed(rejected_history)), "history")

    def _update_table(self, table: DataTable, data: List[QueueItem], type: str):
        # Determine columns based on type
        # Ideally we check what columns are added, but we know the structure.

        # Optimization: Only clear/redraw if counts differ or naive check?
        # For simplicity, we clear and redraw. Textual is fast enough for small lists.
        cursor_coord = table.cursor_coordinate
        table.clear()

        for idx, item in enumerate(data):
            if type == "queue":
                wait_time = f"{idx * AVERAGE_SONG_DURATION_MIN} mins"
                table.add_row(
                    str(idx + 1),
                    item.title,
                    item.username,
                    item.ip,
                    item.url,
                    wait_time,
                    item.added_at,
                    key=str(idx),  # Key matches current list index
                )
            else:  # history types
                table.add_row(
                    item.title,
                    item.username,
                    item.url,
                    item.processed_at or "N/A",
                    key=str(idx),
                )

        # Restore cursor if valid
        if cursor_coord.row < len(data):
            table.move_cursor(row=cursor_coord.row, column=cursor_coord.column)

    def action_play_item(self) -> None:
        # Only allow actions on the Queue tab
        try:
            tabbed = self.query_one(TabbedContent)
            if tabbed.active != "tab-queue":
                return

            table = self.query_one("#queue-table", DataTable)
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if row_key:
                row_index = table.get_row_index(row_key)
                self.process_item(row_index, "play")
        except Exception:
            pass

    def action_delete_item(self) -> None:
        try:
            tabbed = self.query_one(TabbedContent)
            if tabbed.active != "tab-queue":
                return

            table = self.query_one("#queue-table", DataTable)
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if row_key:
                row_index = table.get_row_index(row_key)
                self.process_item(row_index, "reject")
        except Exception:
            pass

    def process_item(self, index: int, action: str) -> None:
        global current_video_id
        with queue_lock:
            if 0 <= index < len(music_playlist):
                item = music_playlist.pop(index)
                item.processed_at = datetime.datetime.now().strftime("%H:%M:%S")

                if action == "play":
                    played_history.append(item)
                    # Update current video ID instead of opening browser
                    vid_id = extract_video_id(item.url)
                    if vid_id:
                        current_video_id = vid_id
                        self.notify(f"Now Playing: {item.title}")
                    else:
                        self.notify(
                            f"Could not extract ID for: {item.title}", severity="error"
                        )
                else:
                    rejected_history.append(item)
                    self.notify(f"Rejected: {item.title}")

                self.refresh_tables()

    def action_export_playlist(self) -> None:
        with queue_lock:
            if not played_history:
                self.notify("Played history is empty. Nothing to export.", severity="warning")
                return

            export_data = []
            for item in played_history:
                artist = "Unknown Artist"
                song = item.title
                if " - " in item.title:
                    parts = item.title.split(" - ", 1)
                    artist = parts[0].strip()
                    song = parts[1].strip()
                
                export_data.append({
                    "song": song,
                    "artist": artist,
                    "url": item.url
                })
            
            try:
                file_name = "played_playlist.json"
                with open(file_name, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=4, ensure_ascii=False)
                self.notify(f"Exported played history to {file_name}", severity="information")
            except Exception as e:
                self.notify(f"Error exporting playlist: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self.add_local_url()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            self.add_local_url()

    def add_local_url(self) -> None:
        input_widget = self.query_one("#url-input", Input)
        url = input_widget.value.strip()
        if url:
            if is_valid_youtube_url(url):
                self.notify("Fetching title...", severity="information")
                input_widget.value = ""  # Clear immediately
                self.add_url_worker(url)
            else:
                self.notify("Invalid YouTube URL", severity="error")

    @work(thread=True)
    def add_url_worker(self, url: str) -> None:
        title = get_youtube_title(url)
        self.call_from_thread(self._finish_add_url, url, title)

    def _finish_add_url(self, url: str, title: str) -> None:
        with queue_lock:
            item = QueueItem(
                url=url,
                title=title,
                ip="Localhost",
                username="Host (You)",
                added_at=datetime.datetime.now().strftime("%H:%M:%S"),
            )
            music_playlist.append(item)

        self.notify(f"Added '{title}'!")
        self.refresh_tables()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    tui_app = MusicQueueApp()
    tui_app.run()