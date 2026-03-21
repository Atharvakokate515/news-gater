"""
Email Agent - Personalized Email Introduction Generator

Purpose:
    Generates warm, engaging email introductions for daily digest emails.
    Creates personalized greetings and previews of top articles.

Key Features:
    - Personalized greeting with user's name and date
    - 2-3 sentence preview of top articles
    - Highlights interesting themes
    - Uses Llama-3-8B (simple text generation task)

Usage:
    agent = EmailAgent(user_profile)
    intro = agent.generate_introduction(ranked_articles)
    digest = agent.create_email_digest_response(articles, total, limit=10)
"""

import os
from datetime import datetime
from typing import List, Optional
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class EmailIntroduction(BaseModel):
    greeting: str = Field(description="Personalized greeting with user's name and date")
    introduction: str = Field(description="2-3 sentence overview of what's in the top 10 ranked articles")


class RankedArticleDetail(BaseModel):
    digest_id: str
    rank: int
    relevance_score: float
    title: str
    summary: str
    url: str
    article_type: str
    reasoning: Optional[str] = None


class EmailDigestResponse(BaseModel):
    introduction: EmailIntroduction
    articles: List[RankedArticleDetail]
    total_ranked: int
    top_n: int
    
    def to_markdown(self) -> str:
        markdown = f"{self.introduction.greeting}\n\n"
        markdown += f"{self.introduction.introduction}\n\n"
        markdown += "---\n\n"
        
        for article in self.articles:
            markdown += f"## {article.title}\n\n"
            markdown += f"{article.summary}\n\n"
            markdown += f"[Read more →]({article.url})\n\n"
            markdown += "---\n\n"
        
        return markdown


class EmailDigest(BaseModel):
    introduction: EmailIntroduction
    ranked_articles: List[dict] = Field(description="Top 10 ranked articles with their details")


PROMPT = """You are an expert email writer creating personalized AI news digests.

Write a warm, professional introduction for a daily AI digest email.

Requirements:
- Greet the user by name
- Include today's date: {current_date}
- Write 2-3 sentences previewing the top articles
- Highlight interesting themes or important topics
- Keep it friendly and engaging

Top Articles to Preview:
{article_summaries}

Output as JSON with "greeting" and "introduction" fields."""


class EmailAgent:
    """
    AI agent that generates personalized email introductions.
    
    Architecture:
        Input: List of top-ranked articles
        Output: Personalized greeting + preview
        
    """
    def __init__(self, user_profile: dict):    # getting User_profile, (Q: from where ???)  'uesrprofile' file provides it
        hf_token = os.getenv("HUGGINGFACE_API_TOKEN")
        if not hf_token:
            raise ValueError("HUGGINGFACE_API_TOKEN not found in .env file")
        
        self.user_profile = user_profile
        
        # Use smaller/faster model for email generation (simpler task)
        self.llm = HuggingFaceEndpoint(
            repo_id="meta-llama/Meta-Llama-3-8B-Instruct",
            huggingfacehub_api_token=hf_token,
            temperature=0.7,
            max_new_tokens=512,
        )
        
        self.parser = JsonOutputParser(pydantic_object=EmailIntroduction)
        self.prompt = ChatPromptTemplate.from_template(PROMPT)
        self.chain = self.prompt | self.llm | self.parser

    def generate_introduction(self, ranked_articles: List) -> EmailIntroduction:   #getting RankedArticles as input (Q: from where ?)  currator provides it
        """  Args:
            ranked_articles: List of article objects (could be RankedArticle or dict)
                            Must have 'title' and 'relevance_score' attributes/keys
        
            Returns:
            EmailIntroduction with greeting and preview text
            Returns fallback introduction if generation fails
        """
        
        if not ranked_articles:
            current_date = datetime.now().strftime('%B %d, %Y')
            return EmailIntroduction(
                greeting=f"Hey {self.user_profile['name']}, here is your daily digest of AI news for {current_date}.",
                introduction="No articles were ranked today."
            )
        
        top_articles = ranked_articles[:10]
        article_summaries = "\n".join([
            #  # “If this is an object with a title attribute, use it. Otherwise, treat it like a dictionary and try to get 'title'. If that fails, use 'N/A'.”
            f"{idx + 1}. {article.title if hasattr(article, 'title') else article.get('title', 'N/A')} (Score: {article.relevance_score if hasattr(article, 'relevance_score') else article.get('relevance_score', 0):.1f}/10)"  
            for idx, article in enumerate(top_articles)
        ])
        
        current_date = datetime.now().strftime('%B %d, %Y')
        
        try:
            result = self.chain.invoke({
                "current_date": current_date,
                "article_summaries": article_summaries
            })
            
            intro = EmailIntroduction(**result)
            
            # Ensure greeting has correct format
            if not intro.greeting.startswith(f"Hey {self.user_profile['name']}"):
                # Override with standard format if LLM didn't follow instructions
                intro.greeting = f"Hey {self.user_profile['name']}, here is your daily digest of AI news for {current_date}."
            
            return intro
            
        except Exception as e:
            print(f"Error generating introduction: {e}")
            return EmailIntroduction(
                greeting=f"Hey {self.user_profile['name']}, here is your daily digest of AI news for {current_date}.",
                introduction="Here are the top 10 AI news articles ranked by relevance to your interests."
            )

    def create_email_digest(self, ranked_articles: List[dict], limit: int = 10) -> EmailDigest:   #getting RankedArticles as input (Q: from where ?)
        top_articles = ranked_articles[:limit]
        introduction = self.generate_introduction(top_articles)
        
        return EmailDigest(
            introduction=introduction,
            ranked_articles=top_articles
        )
    
    def create_email_digest_response(self, ranked_articles: List[RankedArticleDetail], total_ranked: int, limit: int = 10) -> EmailDigestResponse:
        top_articles = ranked_articles[:limit]
        introduction = self.generate_introduction(top_articles)
        
        return EmailDigestResponse(
            introduction=introduction,
            articles=top_articles,
            total_ranked=total_ranked,
            top_n=limit
        )


if __name__ == "__main__":
    from app.profiles.user_profile import USER_PROFILE
    
    agent = EmailAgent(USER_PROFILE)
    
    # Test with mock articles
    test_articles = [
        type('Article', (), {
            'title': 'Building Production RAG Systems',
            'relevance_score': 9.5
        })(),
        type('Article', (), {
            'title': 'New AI Safety Research',
            'relevance_score': 8.7
        })(),
    ]
    
    intro = agent.generate_introduction(test_articles)
    print(f"Greeting: {intro.greeting}")
    print(f"Introduction: {intro.introduction}")
