import re
import requests
import json
from bs4 import BeautifulSoup
from typing import List, Dict


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


def perform_youtube_search(query: str) -> List[Dict[str, str]]:
    """Performs a YouTube search and returns a list of video titles, URLs, and thumbnails."""
    search_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    results = []
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors

        soup = BeautifulSoup(response.text, "html.parser")

        # YouTube's HTML structure can change, making scraping fragile.
        # This attempts to find video results.
        # Look for script tags containing 'var ytInitialData'
        script_tags = soup.find_all('script')
        yt_initial_data = None
        for script in script_tags:
            if 'var ytInitialData' in str(script):
                yt_initial_data = script
                break

        if yt_initial_data:
            # Extract JSON string from the script tag
            json_str = str(yt_initial_data).split('var ytInitialData = ')[1].split(';</script>')[0]
            data = json.loads(json_str)

            # Navigate through the JSON structure to find video results
            # This path is highly dependent on YouTube's internal API and can break.
            contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
            
            for section in contents:
                if 'itemSectionRenderer' in section:
                    for item in section['itemSectionRenderer'].get('contents', []):
                        if 'videoRenderer' in item:
                            video = item['videoRenderer']
                            video_id = video.get('videoId')
                            title = video.get('title', {}).get('runs', [{}])[0].get('text')
                            channel = video.get('ownerText', {}).get('runs', [{}])[0].get('text')
                            thumbnail_url = video.get('thumbnail', {}).get('thumbnails', [{}])[-1].get('url') # Get highest quality thumbnail

                            if video_id and title:
                                results.append({
                                    "title": title,
                                    "channel": channel,
                                    "url": f"https://www.youtube.com/watch?v={video_id}",
                                    "thumbnail": thumbnail_url
                                })
                                if len(results) >= 10: # Limit results
                                    break
                    if len(results) >= 10:
                        break
        
    except requests.exceptions.RequestException as e:
        print(f"Network error during YouTube search: {e}")
    except Exception as e:
        print(f"Error parsing YouTube search results: {e}")
    
    return results
