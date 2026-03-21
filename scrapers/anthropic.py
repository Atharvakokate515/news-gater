from datetime import datetime, timedelta, timezone
from typing import List, Optional
import feedparser
from docling.document_converter import DocumentConverter
from pydantic import BaseModel


class AnthropicArticle(BaseModel):
    title: str
    description: str
    url: str
    guid: str   # GUID = Globally Unique Identifier, used as primary key in Database.
    published_at: datetime
    category: Optional[str] = None


class AnthropicScraper:
    def __init__(self):
        self.rss_urls = [  # Anthropic doesnt allow or show RSS feeds so using Olshansk method.
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
        ]
        self.converter = DocumentConverter()  # Library for converting web pages/PDFs to MARKDOWN.

    #==============================================================================
    # get the articles fmo various feeds
    #==============================================================================
    def get_articles(self, hours: int = 24) -> List[AnthropicArticle]:
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        articles = []
        seen_guids = set()  # same article can appear in multiple feeds → need deduplication
        
        for rss_url in self.rss_urls:     # Parse through every 3 feeds. eg: (feed1= 2articles, feed2= 4articles,feed3= None)
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                continue
            
            for entry in feed.entries: # parse through each article in a feed.
                published_parsed = getattr(entry, "published_parsed", None)
                if not published_parsed:
                    continue
                
                published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                if published_time >= cutoff_time:
                    guid = entry.get("id", entry.get("link", ""))
                    if guid not in seen_guids:    #to check if the articles are already parsed by us.
                        seen_guids.add(guid)
                        articles.append(AnthropicArticle(
                            title=entry.get("title", ""),
                            description=entry.get("description", ""),
                            url=entry.get("link", ""),
                            guid=guid,
                            published_at=published_time,
                            category=entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None
                        ))
        
        return articles

    #==============================================================================
    # convert to MARKDOWN  (since we are using third-party feeds)
    #==============================================================================
    def url_to_markdown(self, url: str) -> Optional[str]:
        try:
            result = self.converter.convert(url)
            return result.document.export_to_markdown()
        except Exception:
            return None
        
        """
        **What happens here**:
        
        1. **Takes the URL from RSS**: `https://anthropic.com/blog/claude-3`
        2. **Makes HTTP request to Anthropic's website** (not the RSS feed!)
        3. **Downloads the full HTML page** (the actual blog post on Anthropic's site)
        4. **Converts HTML → Markdown** (using Docling library)
        5. **Returns the complete article text**

        RSS tells which articles are latest and provides the URL's the func then foes to these URL's and fetches the overall data from the actual website.
        """



if __name__ == "__main__":
    scraper = AnthropicScraper()
    articles: List[AnthropicArticle] = scraper.get_articles(hours=100)
    markdown: str = scraper.url_to_markdown(articles[1].url)
    print(markdown)
