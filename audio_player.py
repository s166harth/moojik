import yt_dlp
import subprocess
import threading
import os
import tempfile
from data_models import queue_lock, music_playlist, played_history
import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioPlayer:
    def __init__(self):
        self.current_process = None
        self.is_playing = False
        self.should_stop = False
        self.autoplay_enabled = False  # New autoplay flag
    
    def extract_and_play_audio(self, video_url, title, username, on_completion_callback=None):
        """Extract audio from YouTube URL and play it using MPV"""
        logger.info(f"Starting playback for: {title}")
        
        # Cancel any currently playing audio
        if self.is_playing:
            self.stop_current_playback()
        
        # Create a thread for audio playback
        def playback_thread():
            self.is_playing = True
            self.should_stop = False
            
            try:
                # Get direct audio URL using yt-dlp without downloading
                ydl_opts = {
                    'format': 'bestaudio/best',
                }
                
                logger.info(f"Getting audio URL for: {title}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    audio_url = info['url']
                
                # Play using MPV with controls visible
                logger.info(f"Playing with MPV: {audio_url}")
                cmd = ['mpv', '--no-video', '--force-window=yes', '--keep-open=no', audio_url]
                
                # Start MPV process and capture output for debugging
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Monitor the process
                try:
                    # Wait for the process to complete and capture output
                    stdout, stderr = process.communicate()

                    # Log the output for debugging
                    logger.info(f"MPV stdout: {stdout.decode()}")
                    logger.info(f"MPV stderr: {stderr.decode()}")

                    if self.should_stop:
                        logger.info("Playback stopped by user")
                    else:
                        logger.info(f"Finished playing: {title}")

                except subprocess.TimeoutExpired:
                    # This shouldn't happen with communicate() but just in case
                    if self.should_stop:
                        logger.info("Playback stopped by user")
                        process.terminate()
                        try:
                            process.communicate(timeout=1)  # Changed from wait to communicate
                        except subprocess.TimeoutExpired:
                            process.kill()
                
                # Mark as not playing anymore
                self.is_playing = False
                
                # Call completion callback if provided and not stopped by user
                if on_completion_callback and not self.should_stop:
                    # Run the callback in a separate thread to avoid blocking
                    callback_thread = threading.Thread(target=on_completion_callback, daemon=True)
                    callback_thread.start()
            
            except subprocess.CalledProcessError as e:
                logger.error(f"MPV error: {e}")
                self.is_playing = False
            except Exception as e:
                logger.error(f"Error in audio playback: {e}")
                self.is_playing = False
    
        # Start playback in a separate thread
        self.current_process = threading.Thread(target=playback_thread, daemon=True)
        self.current_process.start()
    
    def stop_current_playback(self):
        """Stop current audio playback"""
        logger.info("Stopping current playback")
        self.should_stop = True
        self.is_playing = False
    
    def is_currently_playing(self):
        """Check if audio is currently playing"""
        return self.is_playing
    
    def toggle_autoplay(self):
        """Toggle autoplay on/off"""
        self.autoplay_enabled = not self.autoplay_enabled
        status = "enabled" if self.autoplay_enabled else "disabled"
        print(f"Autoplay {status}")
        return self.autoplay_enabled
    
    def is_autoplay_enabled(self):
        """Check if autoplay is enabled"""
        return self.autoplay_enabled


# Global audio player instance
audio_player = AudioPlayer()


def play_next_in_queue():
    """Function to play the next song in queue when current finishes"""
    # Only continue if autoplay is enabled
    if not audio_player.is_autoplay_enabled():
        print("Autoplay is disabled, stopping playback")
        return
        
    with queue_lock:
        if music_playlist:
            # Get the next item in queue
            next_item = music_playlist[0]
            print(f"Auto-playing next: {next_item.title}")
            
            # Play the audio
            audio_player.extract_and_play_audio(
                next_item.url, 
                next_item.title, 
                next_item.username,
                on_completion_callback=play_next_in_queue
            )
            
            # Move item from queue to played history
            item = music_playlist.pop(0)
            item.processed_at = datetime.datetime.now().strftime("%H:%M:%S")
            played_history.append(item)
        else:
            print("Queue is empty, no more songs to play.")