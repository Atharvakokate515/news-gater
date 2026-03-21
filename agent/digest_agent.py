import os
from typing import Optional
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class DigestOutput(BaseModel):
    title: str = Field(description="Compelling title (5-10 words)")
    summary: str = Field(description="2-3 sentence summary")


PROMPT = """You are an expert AI news analyst. Create concise digests for technical AI content.

Guidelines:
- Create a compelling title (5-10 words)
- Write a 2-3 sentence summary highlighting main points
- Focus on actionable insights
- Use clear, accessible language
- Avoid marketing fluff

Output your response as JSON with "title" and "summary" fields. 

Create a digest for this {article_type}:

Title: {title}
Content: {content}"""


class DigestAgent:
    def __init__(self, model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct"):
        hf_token = os.getenv("HUGGINGFACE_API_TOKEN")
        if not hf_token:
            raise ValueError("HUGGINGFACE_API_TOKEN not found in .env file")
        
        self.llm = HuggingFaceEndpoint(
            repo_id=model_name,
            huggingfacehub_api_token=hf_token,
            temperature=0.7,
            max_new_tokens=512,
        )
        
        self.parser = JsonOutputParser(pydantic_object=DigestOutput)
        self.prompt = ChatPromptTemplate.from_template(PROMPT)
        self.chain = self.prompt | self.llm | self.parser

    def generate_digest(self, title: str, content: str, article_type: str) -> Optional[DigestOutput]:
        try:
            result = self.chain.invoke({
                "title": title,
                "content": content[:8000],
                "article_type": article_type
            })
            return DigestOutput(**result)   # Unpack this "dictionary" into "keyword arguments". | eg: DigestOutput(title="...", summary="...")
    
        except Exception as e:
            print(f"Error generating digest: {e}")
            return None


if __name__ == "__main__":
    agent = DigestAgent()
    
    digest = agent.generate_digest(
        title="GPT-4 Technical Report",
        content="Today we announce GPT-4, a large multimodal model...",
        article_type="openai"
    )
    
    if digest:
        print(f"Title: {digest.title}")
        print(f"Summary: {digest.summary}")
