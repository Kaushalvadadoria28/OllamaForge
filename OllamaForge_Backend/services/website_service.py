from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import bs4
import logging
import requests
import re

class WebsiteService:
    def __init__(self):
        self._cache = {}
        # Clean DOM by only extracting main content areas, ignoring navs/footers
        self.bs4_kwargs = {
            "parse_only": bs4.SoupStrainer(
                ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "article", "main", "section"]
            )
        }

    def fetch(self, urls, rag_service=None):
        """Scrape URLs with DOM cleaning, caching, and auto-RAG for huge sites."""
        if not urls:
            return {"type": "error", "content": "No URL provided."}
            
        if isinstance(urls, str):
            urls = [urls]

        all_content = []

        for url in urls:
            if url in self._cache:
                logging.info(f"Website cache hit: {url}")
                all_content.append(self._cache[url])
                continue

            try:
                logging.info(f"Scraping website: {url}")
                session = requests.Session()
                session.verify = False  # Bypass strict local SSL
                
                loader = WebBaseLoader(
                    url, 
                    session=session,
                    bs_kwargs=self.bs4_kwargs
                )
                docs = loader.load()
                
                if not docs:
                    continue
                    
                page_text = "\n\n".join([doc.page_content for doc in docs])
                page_text = re.sub(r'\n{3,}', '\n\n', page_text).strip()
                
                self._cache[url] = page_text
                all_content.append(page_text)
                
            except Exception as e:
                logging.error(f"Error scraping {url}: {e}")

        if not all_content:
            return {"type": "error", "content": "Failed to extract content from the provided URLs."}

        aggregated_text = "\n\n---\n\n".join(all_content)

        # RAG Fallback Logic for massive websites
        if len(aggregated_text) > 8000 and rag_service:
            logging.info("Website content is massive. Chunking and injecting into Vectorstore.")
            rag_service.build_and_persist(aggregated_text)
            return {"type": "rag", "content": "Extensive content has been added to Vectorstore."}

        return {"type": "text", "content": aggregated_text}
