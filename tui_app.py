import json
import datetime
from typing import List, Dict

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

from data_models import (
    queue_lock,
    music_playlist,
    played_history,
    rejected_history,
    current_video_id,
    AVERAGE_SONG_DURATION_MIN,
    QueueItem,
)
from utils import (
    is_valid_youtube_url,
    get_youtube_title,
    extract_video_id,
    perform_youtube_search,
)


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
        ("a", "add_from_search", "Add Selected Search Result"),
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
            with TabPane("YouTube Search", id="tab-search"):
                with Vertical():
                    with Horizontal(id="search-input-container"):
                        yield Input(placeholder="Search YouTube...", id="search-query-input")
                        yield Button("Search", id="search-btn", variant="primary")
                    yield DataTable(id="search-results-table")

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
        r_table.add_columns("Title", "User", "URL", "Rejected At", "Reason")

        # Setup Search Results Table
        s_table = self.query_one("#search-results-table", DataTable)
        s_table.cursor_type = "row"
        s_table.add_columns("Title", "Channel", "URL")

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
            else:  # history types (played and rejected)
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
        elif event.button.id == "search-btn":
            self.action_search_youtube()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            self.add_local_url()
        elif event.input.id == "search-query-input":
            self.action_search_youtube()

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

    # --- New TUI Search and Add from Search functionality ---
    def action_search_youtube(self) -> None:
        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab-search":
            self.notify("Please switch to the 'YouTube Search' tab to search.", severity="warning")
            return

        search_input = self.query_one("#search-query-input", Input)
        query = search_input.value.strip()
        if not query:
            self.notify("Please enter a search query.", severity="warning")
            return
        
        self.notify(f"Searching YouTube for '{query}'...", severity="information")
        search_input.value = "" # Clear search input
        self.query_one("#search-results-table", DataTable).clear() # Clear previous results
        self.search_youtube_worker(query)

    @work(thread=True)
    def search_youtube_worker(self, query: str) -> None:
        try:
            results = perform_youtube_search(query) # Use the shared search function
            self.call_from_thread(self._display_search_results, results)
        except Exception as e:
            self.call_from_thread(self.notify, f"Error during YouTube search: {e}", severity="error")

    def _display_search_results(self, results: List[Dict[str, str]]) -> None:
        s_table = self.query_one("#search-results-table", DataTable)
        s_table.clear()
        if not results:
            self.notify("No YouTube results found.", severity="information")
            return

        for idx, result in enumerate(results):
            s_table.add_row(
                result.get("title", "N/A"),
                result.get("channel", "N/A"),
                result.get("url", "N/A"),
                key=f"search_result_{idx}"
            )
        self.notify(f"Found {len(results)} YouTube results.", severity="information")

    def action_add_from_search(self) -> None:
        tabbed = self.query_one(TabbedContent)
        if tabbed.active != "tab-search":
            return # Only allow adding from the search tab

        s_table = self.query_one("#search-results-table", DataTable)
        row_key = s_table.coordinate_to_cell_key(s_table.cursor_coordinate).row_key
        if row_key:
            row_index = s_table.get_row_index(row_key)
            row_data = s_table.get_row(row_key)
            
            title = row_data[0] # Title is the first column
            url = row_data[2]   # URL is the third column

            with queue_lock:
                item = QueueItem(
                    url=url,
                    title=title,
                    ip="Localhost (TUI Search)",
                    username="Host (You)",
                    added_at=datetime.datetime.now().strftime("%H:%M:%S"),
                )
                music_playlist.append(item)
            self.notify(f"Added '{title}' from search to queue!", severity="success")
            self.refresh_tables() # Refresh all tables to show new item in queue
