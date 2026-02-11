# Moojik Implementation Documentation

## Overview

Moojik is a "democratic" aux cord manager that allows guests to submit YouTube music links while giving the host complete control over the playlist. The system consists of a web interface for guests and a terminal-based TUI for the host.

## Architecture

### Core Components

1. **Data Models** (`data_models.py`)
   - Defines shared data structures and thread-safe state management
   - Contains `QueueItem` dataclass for storing song information
   - Manages global queues: `music_playlist`, `played_history`, `rejected_history`
   - Uses `threading.RLock()` for thread safety

2. **Web Interface** (`flask_app.py`)
   - Flask-based web server accessible to guests
   - Provides form for submitting YouTube links
   - Shows current queue, played history, and rejected items
   - Includes YouTube search functionality
   - Offers playlist download capabilities

3. **Terminal Interface** (`tui_app.py`)
   - Textual-based TUI for the host
   - Displays current queue with song details
   - Allows host to accept (space) or reject (D) songs
   - Provides real-time queue management

4. **Audio Player** (`audio_player.py`)
   - Handles audio playback using MPV
   - Extracts audio from YouTube URLs using yt-dlp
   - Manages playback lifecycle and autoplay functionality

5. **Utilities** (`utils.py`)
   - Helper functions for URL validation, title extraction, and YouTube search
   - Contains utility functions for various operations

## Data Flow

### Song Submission Process

1. Guest visits web interface at `http://<HOST_IP>:5000`
2. Guest enters their name and YouTube URL
3. Form submission triggers validation and title extraction
4. Validated song is added to `music_playlist` queue
5. TUI automatically updates to show new song
6. Host sees song in TUI and decides to accept or reject

### Playback Process

1. Host presses SPACE in TUI to accept a song
2. Audio player extracts audio from YouTube URL
3. MPV plays the audio with `--keep-open=no` to auto-close after playback
4. On completion, song moves from queue to played history
5. If autoplay is enabled, next song in queue plays automatically

### Rejection Process

1. Host presses D in TUI to reject a song
2. Song moves from queue to rejected history
3. Web interface updates to show rejection in history section

## Key Features

### Web Interface Features

- **Song Submission**: Form for guests to add YouTube links with their names
- **Real-time Queue Display**: Shows current queue with positions and estimated wait times
- **YouTube Search**: Integrated search functionality to find and add songs
- **History Display**: Shows played and rejected songs with timestamps
- **Playlist Download**: Multiple download options for current queue and history

### TUI Features

- **Visual Queue**: Table view of current queue with song details
- **Keyboard Controls**: Space to play, D to delete, Q to quit
- **Real-time Updates**: Automatically reflects changes from web interface
- **Host Control**: Complete authority over which songs play

### Audio Player Features

- **Audio Extraction**: Uses yt-dlp to extract audio from YouTube
- **MPV Playback**: Plays audio using MPV player with appropriate flags
- **Autoplay**: Automatic playback of next song when current finishes
- **Process Management**: Handles MPV process lifecycle and termination

## Threading and Concurrency

The application uses multiple threads to handle different components:

- **Main Thread**: Runs the TUI application
- **Flask Thread**: Handles web requests and serves the UI
- **Audio Playback Threads**: Handle individual song playback
- **Shared State**: Protected by `queue_lock` to prevent race conditions

## Configuration and Constants

- `AVERAGE_SONG_DURATION_MIN`: Used for calculating estimated wait times (default: 4 minutes)
- Various MPV flags for optimal audio playback and window management
- Thread-safe data structures for cross-component communication

## Error Handling

- Input validation for YouTube URLs
- Graceful handling of network errors during title extraction
- Process management for MPV to prevent hanging processes
- Thread-safe operations to prevent data corruption

## Network and Discovery

- Flask server runs on port 5000 accessible to local network
- Uses zeroconf/mDNS for service discovery (accessible as `http://moojik.local:5000`)
- IP-based identification of song submitters

## Dependencies

- Flask: Web framework
- Textual: TUI framework
- yt-dlp: YouTube content extraction
- MPV: Audio/video player
- BeautifulSoup4: HTML parsing for metadata extraction
- zeroconf: Service discovery

## Extensibility Points

- Easy addition of new audio players by modifying `audio_player.py`
- Plugin architecture possible through the modular design
- Additional download formats can be added to the web interface
- Queue algorithms can be customized in the data models