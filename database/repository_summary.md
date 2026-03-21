# Repository.py — Summary

This file defines a `Repository` class that acts as the main interface for all
database operations in the project. It uses SQLAlchemy sessions to interact with
models such as YouTubeVideo, OpenAIArticle, AnthropicArticle, and Digest.

## What This File Does

### 1. Creating Records
The repository provides methods to insert:
- YouTube videos  
- OpenAI articles  
- Anthropic articles  
- Digest summaries  

Before inserting, each method checks if the item already exists to avoid
duplicate entries.

### 2. Bulk Insert Operations
The file includes batch-insert functions that:
- Insert multiple videos or articles at once  
- Automatically skip items that already exist  
- Commit only new entries  

### 3. Fetching Items That Need Processing
It provides methods to retrieve:
- YouTube videos without transcripts  
- Anthropic articles without markdown  
- Any article (YouTube/OpenAI/Anthropic) that does not yet have a Digest  

This helps background jobs know which items still require processing.

### 4. Updating Records After Processing
Once external jobs generate new data (transcripts or markdown), the repository
updates:
- YouTube video transcripts  
- Anthropic article markdown content  

### 5. Digest Management
The repository can:
- Create digests (summaries)  
- Retrieve recent digests generated within a given number of hours  

## In One Sentence
This file acts as a database service layer that creates, updates, and retrieves
videos/articles, checks for duplicates, fetches unprocessed content, and manages
digest summaries.
