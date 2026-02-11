import threading
import socket
import datetime
from zeroconf import ServiceInfo, Zeroconf
from flask import (
    Flask,
    request,
    render_template_string,
    flash,
    redirect,
    url_for,
    jsonify,
)

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


# --- Flask Web Server ---
flask_app = Flask(__name__)
flask_app.secret_key = "supersecretkey"

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Queue Submission & Search</title>
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

        /* Search specific styles */
        #search-results { margin-top: 1rem; }
        .search-result-item {
            display: flex;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .search-result-item:hover {
            background-color: #f1f1f1;
        }
        .search-result-item img {
            width: 80px;
            height: 45px;
            margin-right: 10px;
            border-radius: 4px;
            object-fit: cover;
        }
        .search-result-item .details {
            flex-grow: 1;
        }
        .search-result-item .title {
            font-weight: bold;
            color: #333;
        }
        .search-result-item .channel {
            font-size: 0.9em;
            color: #666;
        }
        .search-result-item .add-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background 0.2s;
        }
        .search-result-item .add-btn:hover {
            background: #218838;
        }
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #4CAF50;
            color: white;
            padding: 15px;
            border-radius: 5px;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.5s ease-in-out;
        }
        .notification.show {
            opacity: 1;
        }
        .notification.error {
            background-color: #f44336;
        }
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
        
        <form method="post" id="add-url-form">
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
            <h2>YouTube Search</h2>
            <div class="form-group">
                <label for="search-query">Search YouTube:</label>
                <input type="text" id="search-query" placeholder="Search for songs or artists...">
            </div>
            <button id="search-button">Search</button>
            <div id="search-results">
                <!-- Search results will be loaded here -->
            </div>
        </div>

        <div class="section">
            <h2>Current Queue</h2>
            <div id="current-queue-section">
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

    <div id="notification" class="notification"></div>

    <script>
        document.getElementById('search-button').addEventListener('click', searchYouTube);
        document.getElementById('search-query').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchYouTube();
            }
        });

        // Function to show notifications
        function showNotification(message, isError = false) {
            const notificationDiv = document.getElementById('notification');
            notificationDiv.textContent = message;
            notificationDiv.className = 'notification show';
            if (isError) {
                notificationDiv.classList.add('error');
            } else {
                notificationDiv.classList.remove('error');
            }
            setTimeout(() => {
                notificationDiv.classList.remove('show');
            }, 3000);
        }

        // Function to refresh the queue display
        async function refreshQueueDisplay() {
            try {
                const response = await fetch('/api/queue_data');
                const data = await response.json();
                if (data.queue_html) {
                    document.getElementById('current-queue-section').innerHTML = data.queue_html;
                }
            } catch (error) {
                console.error('Error refreshing queue display:', error);
                showNotification('Error refreshing queue display.', true);
            }
        }

        async function searchYouTube() {
            const query = document.getElementById('search-query').value;
            if (!query) {
                showNotification('Please enter a search query.', true);
                return;
            }

            const searchResultsDiv = document.getElementById('search-results');
            searchResultsDiv.innerHTML = '<p>Searching...</p>';

            try {
                const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`);
                const data = await response.json();

                searchResultsDiv.innerHTML = '';
                if (data.results && data.results.length > 0) {
                    data.results.forEach(result => {
                        const itemDiv = document.createElement('div');
                        itemDiv.className = 'search-result-item';
                        itemDiv.innerHTML = `
                            <img src="${result.thumbnail}" alt="Thumbnail">
                            <div class="details">
                                <div class="title">${result.title}</div>
                                <div class="channel">${result.channel}</div>
                            </div>
                            <button class="add-btn" data-title="${result.title}" data-url="${result.url}">Add to Queue</button>
                        `;
                        searchResultsDiv.appendChild(itemDiv);
                    });

                    // Add event listeners to the new "Add to Queue" buttons
                    searchResultsDiv.querySelectorAll('.add-btn').forEach(button => {
                        button.addEventListener('click', function() {
                            const title = this.dataset.title;
                            const url = this.dataset.url;
                            addSearchResultToQueue(title, url);
                        });
                    });

                } else {
                    searchResultsDiv.innerHTML = '<p>No results found.</p>';
                }
            } catch (error) {
                console.error('Error during YouTube search:', error);
                showNotification('Error searching YouTube.', true);
                searchResultsDiv.innerHTML = '<p class="error">Error searching YouTube.</p>';
            }
        }

        async function addSearchResultToQueue(title, url) {
            const usernameInput = document.getElementById('username');
            const username = usernameInput ? usernameInput.value : 'Anonymous';

            if (!username) {
                showNotification('Please enter your name before adding a song from search results.', true);
                return;
            }

            try {
                const response = await fetch('/api/add_to_queue', { // Use new API endpoint
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        username: username,
                        url: url,
                        title_from_search: title
                    })
                });
                const result = await response.json(); // Expect JSON response

                if (result.status === 'success') {
                    showNotification(result.message);
                    refreshQueueDisplay(); // Refresh the queue display without full page reload
                } else {
                    showNotification(result.message, true);
                }
            } catch (error) {
                console.error('Error adding song from search results:', error);
                showNotification('Error adding song to queue.', true);
            }
        }

        // Initial refresh of the queue when the page loads
        document.addEventListener('DOMContentLoaded', refreshQueueDisplay);
    </script>
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
        .status { margin-top: 20px; font-size: 1.2em; color: #888; text-align: center; }
        .now-playing { font-size: 1.5em; color: #4CAF50; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div id="player-container">
        <div class="status">
            <div class="now-playing">Now Playing: <span id="current-song">Waiting for music...</span></div>
            <div>Audio is playing on the host device</div>
        </div>
    </div>

    <script>
        let currentVideoId = null;
        let currentTitle = null;

        function pollForUpdates() {
            fetch('/api/current')
                .then(response => response.json())
                .then(data => {
                    if (data.video_id && data.video_id !== currentVideoId) {
                        currentVideoId = data.video_id;
                        updatePlayer(data.title || 'Unknown Title');
                    }
                })
                .catch(err => console.error("Error polling:", err));
        }

        function updatePlayer(title) {
            const titleElement = document.getElementById('current-song');
            titleElement.textContent = title;
        }

        // Poll every 2 seconds
        setInterval(pollForUpdates, 2000);
    </script>
</body>
</html>
"""


@flask_app.route("/api/search")
def search_youtube_api():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query parameter is missing"}), 400
    
    search_results = perform_youtube_search(query)
    return jsonify({"results": search_results})


@flask_app.route("/", methods=["GET"]) # Changed to only GET
def index():
    with queue_lock:
        return render_template_string(
            HTML_TEMPLATE,
            playlist=list(music_playlist),
            played=list(played_history),
            rejected=list(rejected_history),
            avg_duration=AVERAGE_SONG_DURATION_MIN,
        )


@flask_app.route("/player")
def player():
    return render_template_string(PLAYER_TEMPLATE)


@flask_app.route("/api/current")
def current_song():
    with queue_lock:
        # Find the currently playing item to get its title
        current_title = "Waiting for music..."
        if current_video_id and played_history:
            # Look for the most recently played item
            for item in reversed(played_history):
                if extract_video_id(item.url) == current_video_id:
                    current_title = item.title
                    break
        
        return jsonify({"video_id": current_video_id, "title": current_title})


@flask_app.route("/api/add_to_queue", methods=["POST"])
def add_to_queue_api():
    url = request.form.get("url", "").strip()
    username = request.form.get("username", "Anonymous").strip()
    title_from_search = request.form.get("title_from_search")
    user_ip = request.remote_addr or "Unknown"

    if not url:
        return jsonify({"status": "error", "message": "URL is missing."}), 400
    
    if not is_valid_youtube_url(url):
        return jsonify({"status": "error", "message": "Invalid YouTube URL."}), 400

    title = title_from_search if title_from_search else get_youtube_title(url)

    with queue_lock:
        item = QueueItem(
            url=url,
            title=title,
            ip=str(user_ip),
            username=username,
            added_at=datetime.datetime.now().strftime("%H:%M:%S"),
        )
        music_playlist.append(item)
    
    return jsonify({"status": "success", "message": f"Successfully added '{title}'!"})


@flask_app.route("/api/queue_data")
def queue_data_api():
    with queue_lock:
        # Render only the queue table part of the template
        queue_html = render_template_string(
            """
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
            """,
            playlist=list(music_playlist),
            avg_duration=AVERAGE_SONG_DURATION_MIN,
        )
    return jsonify({"queue_html": queue_html})


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



if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    from tui_app import MusicQueueApp
    tui_app = MusicQueueApp()
    tui_app.run()