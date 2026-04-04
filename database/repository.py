from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from .models import YouTubeVideo, OpenAIArticle, AnthropicArticle, Digest
from .connection import get_session


class Repository:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()


    #===================================================================================
    # Add one YouTube video to database.
    #===================================================================================
    def create_youtube_video(self, video_id: str, title: str, url: str, channel_id: str, 
                            published_at: datetime, description: str = "", transcript: Optional[str] = None) -> Optional[YouTubeVideo]:
        """
        Returns:
            YouTubeVideo object if created
            None if already exists (duplicate check)
        
        Process:
            1. Check if video_id exists (prevent duplicates)
            2. If exists, return None
            3. If not, create YouTubeVideo object
            4. Add to session and commit (save)
        """
        existing = self.session.query(YouTubeVideo).filter_by(video_id=video_id).first()
        if existing:
            return None
        video = YouTubeVideo(
            video_id=video_id,
            title=title,
            url=url,
            channel_id=channel_id,
            published_at=published_at,
            description=description,
            transcript=transcript
        )
        self.session.add(video)
        self.session.commit()
        return video


    #===================================================================================
    # Add one OpenAI article.
    #===================================================================================
    def create_openai_article(self, guid: str, title: str, url: str, published_at: datetime,
                              description: str = "", category: Optional[str] = None) -> Optional[OpenAIArticle]:
        existing = self.session.query(OpenAIArticle).filter_by(guid=guid).first()
        if existing:
            return None
        article = OpenAIArticle(
            guid=guid,
            title=title,
            url=url,
            published_at=published_at,
            description=description,
            category=category
        )
        self.session.add(article)
        self.session.commit()
        return article


    #===================================================================================
    # Add one Anthropic article.
    #===================================================================================
    def create_anthropic_article(self, guid: str, title: str, url: str, published_at: datetime,
                                description: str = "", category: Optional[str] = None) -> Optional[AnthropicArticle]:
        existing = self.session.query(AnthropicArticle).filter_by(guid=guid).first()
        if existing:
            return None
        article = AnthropicArticle(
            guid=guid,
            title=title,
            url=url,
            published_at=published_at,
            description=description,
            category=category
        )
        self.session.add(article)
        self.session.commit()
        return article



    #===================================================================================
    # Add multiple videos efficiently (single transaction).
    #===================================================================================
    def bulk_create_youtube_videos(self, videos: List[dict]) -> int:
        """
        Args:
            videos: List of dicts with video data
        
        Returns:
            Number of NEW videos created (skips duplicates)
        
        Why bulk?
            Individual: 50 videos = 50 INSERT queries (slow)
            Bulk: 50 videos = 1 INSERT query (fast!)
        """
        new_videos = []
        for v in videos:
            existing = self.session.query(YouTubeVideo).filter_by(video_id=v["video_id"]).first()
            if not existing:
                new_videos.append(YouTubeVideo(
                    video_id=v["video_id"],
                    title=v["title"],
                    url=v["url"],
                    channel_id=v.get("channel_id", ""),
                    published_at=v["published_at"],
                    description=v.get("description", ""),
                    transcript=v.get("transcript")
                ))
        if new_videos:
            self.session.add_all(new_videos)
            self.session.commit()
        return len(new_videos)


    #===================================================================================
         #same pattern as bulk_create_youtube_videos
    #===================================================================================
    def bulk_create_openai_articles(self, articles: List[dict]) -> int:
        new_articles = []
        for a in articles:
            existing = self.session.query(OpenAIArticle).filter_by(guid=a["guid"]).first()
            if not existing:
                new_articles.append(OpenAIArticle(
                    guid=a["guid"],
                    title=a["title"],
                    url=a["url"],
                    published_at=a["published_at"],
                    description=a.get("description", ""),
                    category=a.get("category")
                ))
        if new_articles:
            self.session.add_all(new_articles)
            self.session.commit()
        return len(new_articles)


    #===================================================================================
    #===================================================================================
    def bulk_create_anthropic_articles(self, articles: List[dict]) -> int:
        new_articles = []
        for a in articles:
            existing = self.session.query(AnthropicArticle).filter_by(guid=a["guid"]).first()
            if not existing:
                new_articles.append(AnthropicArticle(
                    guid=a["guid"],
                    title=a["title"],
                    url=a["url"],
                    published_at=a["published_at"],
                    description=a.get("description", ""),
                    category=a.get("category")
                ))
        if new_articles:
            self.session.add_all(new_articles)
            self.session.commit()
        return len(new_articles)


    #===================================================================================
            # Find articles missing full markdown content.
    #===================================================================================
    def get_anthropic_articles_without_markdown(self, limit: Optional[int] = None) -> List[AnthropicArticle]:
        """
        Why?
            1. Scraper saves article with description (fast)
            2. Later, fetch full markdown from URL (slow)
            3. This finds articles needing step 2
        SQL:
            SELECT * FROM anthropic_articles 
            WHERE markdown IS NULL
        """
        query = self.session.query(AnthropicArticle).filter(AnthropicArticle.markdown.is_(None))
        if limit:
            query = query.limit(limit)
        return query.all()


    #===================================================================================
            # Add full markdown to existing article.
    #===================================================================================
    def update_anthropic_article_markdown(self, guid: str, markdown: str) -> bool:
        """
        Process:
        1. Scraper saves article with short description
        2. url_to_markdown() fetches full article
        3. This method updates the record
        """
        article = self.session.query(AnthropicArticle).filter_by(guid=guid).first()
        if article:
            article.markdown = markdown
            self.session.commit()
            return True
        return False


    #===================================================================================
         # videos missing transcripts.
    #===================================================================================
    def get_youtube_videos_without_transcript(self, limit: Optional[int] = None) -> List[YouTubeVideo]:
        """
        Find videos missing transcripts.
        Why?
            Two-stage processing:
            1. Save video metadata (fast)
            2. Fetch transcript later (slow)
        This finds videos stuck at stage 1.
        SQL Generated:
            SELECT * FROM youtube_videos 
            WHERE transcript IS NULL
            LIMIT 10
        """
        query = self.session.query(YouTubeVideo).filter(YouTubeVideo.transcript.is_(None))
        if limit:
            query = query.limit(limit)
        return query.all()


    #===================================================================================
    # Add transcript to existing video.
    #===================================================================================
    def update_youtube_video_transcript(self, video_id: str, transcript: str) -> bool:
        """
        Args:
            transcript: Text OR "__UNAVAILABLE__" if no transcript exists
        Returns:
            True if updated, False if video not found
        Special marker:
            "__UNAVAILABLE__" = checked but no transcript available
            Prevents re-checking same video repeatedly
        """
        video = self.session.query(YouTubeVideo).filter_by(video_id=video_id).first()
        if video:
            video.transcript = transcript
            self.session.commit()
            return True
        return False


    #===================================================================================
    # Find ALL articles (YouTube, OpenAI, Anthropic) that need digests.
    #===================================================================================
    def get_articles_without_digest(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
         This is COMPLEX because:
            - Queries 3 different tables
            - Checks which already have digests
            - Unifies different schemas
            - Returns common format
        Returns:
            List of dicts:
            {
                "type": "youtube" | "openai" | "anthropic",
                "id": article_id,
                "title": title,
                "url": url,
                "content": text for digest generation,
                "published_at": datetime
            }
        """

        """
        **Why so complex?**
        ```
        Three different tables:
        youtube_videos      → has transcript
        openai_articles     → has description  
        anthropic_articles  → has markdown
        
        Need to:
        1. Check digests table for what's done
        2. Query each source separately
        3. Unify into common format
        4. Return combined list
        ```
        
        **Visual Flow:**
        ```
        Digests Table                  Articles Without Digests
            ↓                                    ↓
        youtube:abc123        →      youtube:def456 ✓ (not in digests)
        openai:xyz789         →      youtube:ghi789 ✓ (not in digests)
                                      openai:jkl012 ✓ (not in digests)
                                      anthropic:mno345 ✓ (not in digests)
        """
        articles = []
        seen_ids = set()
        
        digests = self.session.query(Digest).all()
        for d in digests:
            seen_ids.add(f"{d.article_type}:{d.article_id}")
        
        youtube_videos = self.session.query(YouTubeVideo).filter(
            YouTubeVideo.transcript.isnot(None),
            YouTubeVideo.transcript != "__UNAVAILABLE__"
        ).all()
        for video in youtube_videos:
            key = f"youtube:{video.video_id}"
            if key not in seen_ids:
                articles.append({
                    "type": "youtube",
                    "id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "content": video.transcript or video.description or "",
                    "published_at": video.published_at
                })
        
        openai_articles = self.session.query(OpenAIArticle).all()
        for article in openai_articles:
            key = f"openai:{article.guid}"
            if key not in seen_ids:
                articles.append({
                    "type": "openai",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.description or "",
                    "published_at": article.published_at
                })
        
        anthropic_articles = self.session.query(AnthropicArticle).filter(
            AnthropicArticle.markdown.isnot(None) 
        ).all()
        for article in anthropic_articles:
            key = f"anthropic:{article.guid}"
            if key not in seen_ids:
                articles.append({
                    "type": "anthropic",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.markdown or article.description or "",
                    "published_at": article.published_at
                })
        
        if limit:
            articles = articles[:limit]
        
        return articles


    #===================================================================================
        # Save AI-generated digest for an article.
    #===================================================================================
    def create_digest(self, article_type: str, article_id: str, url: str, title: str, summary: str, published_at: Optional[datetime] = None) -> Optional[Digest]:
        """
        Args:
            article_type: "youtube", "openai", or "anthropic"
            article_id: Original article's ID
            url: Link to original
            title: NEW title (from DigestAgent, not original)
            summary: AI-generated summary
            published_at: Original publication date
        Digest ID:
            Format: "article_type:article_id"
            Examples:
                "youtube:abc123"
                "openai:https://openai.com/blog/gpt-4"
                "anthropic:https://anthropic.com/news/claude"
        Why composite ID?
            - Prevents duplicates
            - Easy to trace back to source
            - article_id alone might not be unique across sources
        """
        digest_id = f"{article_type}:{article_id}"
        existing = self.session.query(Digest).filter_by(id=digest_id).first()
        if existing:
            return None
        
        if published_at:
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            created_at = published_at
        else:
            created_at = datetime.now(timezone.utc)
        
        digest = Digest(
            id=digest_id,
            article_type=article_type,
            article_id=article_id,
            url=url,
            title=title,
            summary=summary,
            created_at=created_at
        )
        self.session.add(digest)
        self.session.commit()
        return digest


    #===================================================================================
        #Get digests created within last N hours. Used by CuratorAgent to rank articles.
    #===================================================================================
    def get_recent_digests(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Args:
            hours: Time window (default 24 hours = 1 day)
        Returns:
            List of dicts with all digest data:
            {
                "id": "youtube:abc123",
                "article_type": "youtube",
                "article_id": "abc123",
                "url": "https://...",
                "title": "New AI Model Released",
                "summary": "Researchers announce...",
                "created_at": datetime(...)
            }
        SQL:
            SELECT * FROM digests 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        digests = self.session.query(Digest).filter(
            Digest.created_at >= cutoff_time
        ).order_by(Digest.created_at.desc()).all()
        
        return [
            {
                "id": d.id,
                "article_type": d.article_type,
                "article_id": d.article_id,
                "url": d.url,
                "title": d.title,
                "summary": d.summary,
                "created_at": d.created_at
            }
            for d in digests
        ]

