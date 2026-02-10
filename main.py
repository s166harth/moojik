import threading
from flask_app import run_flask
from tui_app import MusicQueueApp


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    tui_app = MusicQueueApp()
    tui_app.run()
