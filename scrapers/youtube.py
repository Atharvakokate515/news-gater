from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import feedparser
from pydantic import BaseModel
import subprocess
import json
import tempfile


class Transcript(BaseModel):
    text: str


class ChannelVideo(BaseModel):
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None


class YouTubeScraper:
    """
    Simple YouTube scraper using yt-dlp for reliable transcript extraction.
    Maintains exact same interface as before - no changes needed in other files.
    """
    
    def __init__(self):
        """Initialize scraper - checks if yt-dlp is available"""
        self._check_ytdlp()
    
    def _check_ytdlp(self):
        """Check if yt-dlp is installed"""
        try:
            subprocess.run(['yt-dlp', '--version'], 
                         capture_output=True, 
                         check=True, 
                         timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  WARNING: yt-dlp not found. Install with: pip install yt-dlp")
            print("⚠️  Transcripts will not be available until yt-dlp is installed.")

    def _get_rss_url(self, channel_id: str) -> str:
        """Get RSS feed URL from channel ID"""
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from various YouTube URL formats"""
        if "youtube.com/watch?v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtube.com/shorts/" in video_url:
            return video_url.split("shorts/")[1].split("?")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return video_url

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        """
        Get transcript for a video using yt-dlp.
        More reliable than youtube-transcript-api.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Transcript object or None if unavailable
        """
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Create temporary directory for subtitle files
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = os.path.join(temp_dir, video_id)
                
                # Download subtitles using yt-dlp
                cmd = [
                    'yt-dlp',
                    '--skip-download',           # Don't download video
                    '--write-auto-subs',         # Get auto-generated subs
                    '--write-subs',              # Get manual subs if available
                    '--sub-lang', 'en',          # English only
                    '--sub-format', 'json3',     # JSON format for easy parsing
                    '--output', output_path,     # Output location
                    '--quiet',                   # Suppress output
                    '--no-warnings',             # Suppress warnings
                    url
                ]
                
                # Run yt-dlp
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Look for subtitle files (manual or auto-generated)
                subtitle_files = [
                    f"{output_path}.en.json3",      # Manual English
                    f"{output_path}.en-US.json3",   # Manual English (US)
                    f"{output_path}.en-GB.json3",   # Manual English (GB)
                ]
                
                # Try to read any available subtitle file
                for subtitle_file in subtitle_files:
                    if os.path.exists(subtitle_file):
                        with open(subtitle_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # Extract text from JSON3 format
                            text_segments = []
                            for event in data.get('events', []):
                                if 'segs' in event:
                                    for seg in event['segs']:
                                        if 'utf8' in seg:
                                            text_segments.append(seg['utf8'])
                            
                            if text_segments:
                                full_text = " ".join(text_segments).strip()
                                # Clean up extra whitespace
                                full_text = " ".join(full_text.split())
                                return Transcript(text=full_text)
                
                # No transcript found
                return None
                
        except subprocess.TimeoutExpired:
            print(f"⚠️  Timeout getting transcript for {video_id}")
            return None
        except FileNotFoundError:
            print(f"❌ yt-dlp not installed. Run: pip install yt-dlp")
            return None
        except Exception as e:
            print(f"⚠️  Error getting transcript for {video_id}: {str(e)}")
            return None

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> List[ChannelVideo]:
        """
        Get latest videos from a channel within specified time window.
        
        Args:
            channel_id: YouTube channel ID
            hours: How many hours back to look
            
        Returns:
            List of ChannelVideo objects (without transcripts)
        """
        feed = feedparser.parse(self._get_rss_url(channel_id))
        if not feed.entries:
            return []
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos = []
        
        for entry in feed.entries:
            # Skip YouTube Shorts
            if "/shorts/" in entry.link:
                continue
            
            # Parse publish time
            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            
            # Only include videos within time window
            if published_time >= cutoff_time:
                video_id = self._extract_video_id(entry.link)
                videos.append(ChannelVideo(
                    title=entry.title,
                    url=entry.link,
                    video_id=video_id,
                    published_at=published_time,
                    description=entry.get("summary", "")
                ))
        
        return videos

    def scrape_channel(self, channel_id: str, hours: int = 150) -> List[ChannelVideo]:
        """
        Scrape channel for videos and get their transcripts.
        
        Args:
            channel_id: YouTube channel ID
            hours: How many hours back to look
            
        Returns:
            List of ChannelVideo objects with transcripts
        """
        videos = self.get_latest_videos(channel_id, hours)
        result = []
        
        print(f"Found {len(videos)} videos, getting transcripts...")
        
        for i, video in enumerate(videos, 1):
            print(f"  [{i}/{len(videos)}] Processing: {video.title[:50]}...")
            
            transcript = self.get_transcript(video.video_id)
            
            # Create updated video with transcript
            result.append(video.model_copy(
                update={"transcript": transcript.text if transcript else None}
            ))
            
            if transcript:
                print(f"    ✅ Transcript found ({len(transcript.text)} chars)")
            else:
                print(f"    ⚠️  No transcript available")
        
        with_transcripts = sum(1 for v in result if v.transcript)
        print(f"\nCompleted: {with_transcripts}/{len(result)} videos with transcripts")
        
        return result


if __name__ == "__main__":
    print("YouTube Scraper Test\n")
    print("=" * 60)
    
    scraper = YouTubeScraper()
    
    # Test 1: Single video transcript
    print("\nTest 1: Getting single video transcript")
    print("-" * 60)
    test_video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    transcript = scraper.get_transcript(test_video_id)
    
    if transcript:
        print(f"✅ Success!")
        print(f"   Length: {len(transcript.text)} characters")
        print(f"   Preview: {transcript.text[:200]}...")
    else:
        print("❌ No transcript available")
    
    # Test 2: Channel scraping
    print("\n" + "=" * 60)
    print("Test 2: Scraping channel videos")
    print("-" * 60)
    channel_id = "UCn8ujwUInbJkBhffxqAPBVQ"  # Your channel
    
    channel_videos = scraper.scrape_channel(
        channel_id,
        hours=200
    )
    
    print("\n" + "=" * 60)
    print("Results:")
    print("-" * 60)
    print(f"Total videos: {len(channel_videos)}")
    print(f"With transcripts: {sum(1 for v in channel_videos if v.transcript)}")
    print(f"Without transcripts: {sum(1 for v in channel_videos if not v.transcript)}")
    
    if channel_videos:
        print("\nSample video:")
        sample = channel_videos[0]
        print(f"  Title: {sample.title}")
        print(f"  Published: {sample.published_at}")
        print(f"  Transcript: {'Yes' if sample.transcript else 'No'}")
        if sample.transcript:
            print(f"  Transcript length: {len(sample.transcript)} chars")












# from datetime import datetime, timedelta, timezone
# from typing import List, Optional
# import os
# import feedparser
# from pydantic import BaseModel
# from youtube_transcript_api import YouTubeTranscriptApi
# from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
# # from youtube_transcript_api.proxies import WebshareProxyConfig


# class Transcript(BaseModel):
#     text: str


# class ChannelVideo(BaseModel):
#     title: str
#     url: str
#     video_id: str
#     published_at: datetime
#     description: str
#     transcript: Optional[str] = None


# class YouTubeScraper:
#     class YouTubeScraper:
#         def __init__(self):
#             self.transcript_api = YouTubeTranscriptApi()

#     #===================================================================================
#     #get the RSS feed URL from Channel_ID
#     #===================================================================================
#     def _get_rss_url(self, channel_id: str) -> str:
#         return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        
#     #===================================================================================
#     #extract video_id from the URL
#     #===================================================================================
#     def _extract_video_id(self, video_url: str) -> str:
#         if "youtube.com/watch?v=" in video_url:
#             return video_url.split("v=")[1].split("&")[0]
#         if "youtube.com/shorts/" in video_url:
#             return video_url.split("shorts/")[1].split("?")[0]
#         if "youtu.be/" in video_url:
#             return video_url.split("youtu.be/")[1].split("?")[0]
#         return video_url

#     #===================================================================================
#     #gets transcript from video_id
#     #===================================================================================
#     def get_transcript(self, video_id: str) -> Optional[Transcript]:
#         try:
#             transcript = self.transcript_api.fetch(video_id)   # returns YoutubeTranscriptApi object, that contains a list of snippets(dict) that contains {text,start,duration}.
#             text = " ".join([snippet.text for snippet in transcript.snippets])  # you join all the "text" to form a transcript.
#             return Transcript(text=text)   # pydantic model returned.
#         except (TranscriptsDisabled, NoTranscriptFound):  # handles the exception to avoid code crash.
#             return None
#         except Exception:
#             return None


#     #===================================================================================
#     # Parses the Channel, for the latest(24hrs) Videos, returns ChannelVideo object
#     #===================================================================================
#     def get_latest_videos(self, channel_id: str, hours: int = 24) -> list[ChannelVideo]:
#         feed = feedparser.parse(self._get_rss_url(channel_id))  # uses FeedParser lib to parse through the RSS feed of the "CHANNEL_ID"
#         if not feed.entries:
#             return []
        
#         cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)  # only the last 24hrs.
#         videos = []
        
#         for entry in feed.entries:
#             if "/shorts/" in entry.link:   #ignore the youtube Shorts
#                 continue
#             published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc) # This line converts the RSS timestamp (published_parsed) into a timezone-aware UTC datetime object..
#             if published_time >= cutoff_time:
#                 video_id = self._extract_video_id(entry.link)  #extract the video id from the link
#                 videos.append(ChannelVideo(
#                     title=entry.title,
#                     url=entry.link,
#                     video_id=video_id,
#                     published_at=published_time,
#                     description=entry.get("summary", "")
#                 ))
        
#         return videos

#     #===================================================================================
#     #Scraped Videos into Transcipts
#     #===================================================================================
#     def scrape_channel(self, channel_id: str, hours: int = 150) -> list[ChannelVideo]:
#         videos = self.get_latest_videos(channel_id, hours)
#         result = []
#         for video in videos:
#             transcript = self.get_transcript(video.video_id)
#             #IMPORTANT - Pydantic feature (.model_copy)
#             result.append(video.model_copy(update={"transcript": transcript.text if transcript else None})) # in our earlier model we didnt have "transcript", we created a copy of our pydantic model, [video.transcript = None | result.transcript = "..."]
#         return result   # a updated pydantic model (with "transcript" added)

# """
# "Why get_latest_videos and scrape_chanel functions seperate ?"

# def get_latest_videos --> Faster, RSS feed parsing is done faster, requires only 1 api call.
# def scrape_channel ---> Slower, getting transcripts is slow and require many API calls.
# """
    
    
# if __name__ == "__main__":
#     scraper = YouTubeScraper()
#     transcript = scraper.get_transcript("3jZ5vnv-LZc")
#     # transcript = scraper.get_transcript("dQw4w9WgXcQ")

#     if transcript:
#         print(transcript.text)
#     else:
#         print("❌ No transcript available")


#     channel_videos = scraper.scrape_channel(
#         "UCn8ujwUInbJkBhffxqAPBVQ",
#         hours=200
#     )
#     print(f"Fetched {len(channel_videos)} videos")


    
