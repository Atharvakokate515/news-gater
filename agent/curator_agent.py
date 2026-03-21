import os
from typing import List
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class RankedArticle(BaseModel):
    digest_id: str = Field(description="The ID of the digest (article_type:article_id)")
    relevance_score: float = Field(description="Relevance score from 0.0 to 10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position (1 = most relevant)", ge=1)
    reasoning: str = Field(description="Brief explanation of why this article is ranked here")


class RankedDigestList(BaseModel):
    articles: List[RankedArticle] = Field(description="List of ranked articles")


PROMPT = """You are an expert AI news curator. Rank articles based on the user's profile.

Scoring Guidelines:
- 9.0-10.0: Highly relevant to user's interests
- 7.0-8.9: Very relevant
- 5.0-6.9: Moderately relevant
- 3.0-4.9: Somewhat relevant
- 0.0-2.9: Low relevance

User Profile:
Name: {name}
Background: {background}
Expertise: {expertise_level}

Interests:
{interests}

Preferences:
{preferences}

Rank these {num_digests} articles:

{digest_list}

Output as JSON with "articles" array. Each must have: digest_id, relevance_score (0.0-10.0), rank (1 to {num_digests}), reasoning."""


class CuratorAgent:   # Thr currator agent needs "USER_PROFILE" as arg.
    def __init__(self, user_profile: dict):
        hf_token = os.getenv("HUGGINGFACE_API_TOKEN")
        if not hf_token:
            raise ValueError("HUGGINGFACE_API_TOKEN not found in .env file")
        
        self.user_profile = user_profile
        
        # Use larger model for better ranking (70B > 8B for complex reasoning)
        self.llm = HuggingFaceEndpoint(
            repo_id="meta-llama/Meta-Llama-3-8B-Instruct",
            huggingfacehub_api_token=hf_token,
            temperature=0.3,
            max_new_tokens=4096,
        )
        
        self.parser = JsonOutputParser(pydantic_object=RankedDigestList)
        self.prompt = ChatPromptTemplate.from_template(PROMPT)
        self.chain = self.prompt | self.llm | self.parser


    
    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []
        
        interests = "\n".join(f"- {i}" for i in self.user_profile["interests"])
        preferences = "\n".join(f"- {k}: {v}" for k, v in self.user_profile["preferences"].items())
        digest_list = "\n\n".join([
            f"ID: {d['id']}\nTitle: {d['title']}\nSummary: {d['summary']}\nType: {d['article_type']}"
            for d in digests
        ])
        
        try:
            result = self.chain.invoke({
                "name": self.user_profile["name"],
                "background": self.user_profile["background"],
                "expertise_level": self.user_profile["expertise_level"],
                "interests": interests,
                "preferences": preferences,
                "num_digests": len(digests),
                "digest_list": digest_list
            })
            
            articles = [RankedArticle(**a) for a in result["articles"]] # RankedDigest object
            articles.sort(key=lambda x: x.rank)  #rank the articles in the list as per rank
            return articles   # list of ranked articles
            
        except Exception as e:
            print(f"Error ranking digests: {e}")
            return []


if __name__ == "__main__":
    from app.profiles.user_profile import USER_PROFILE
    
    curator = CuratorAgent(USER_PROFILE)
    
    test_digests = [
        {
            "id": "youtube:test1",
            "title": "Building RAG Systems",
            "summary": "Practical guide to RAG implementation.",
            "article_type": "youtube"
        },
        {
            "id": "openai:test2",
            "title": "GPT-5 Launch",
            "summary": "Product announcement and pricing.",
            "article_type": "openai"
        }
    ]
    
    ranked = curator.rank_digests(test_digests)
    for a in ranked:
        print(f"{a.rank}. {a.relevance_score}/10 - {a.digest_id}")
