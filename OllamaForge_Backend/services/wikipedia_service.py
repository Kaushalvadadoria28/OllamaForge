from langchain_community.retrievers import WikipediaRetriever
import logging

class WikipediaService:
    def __init__(self):
        self.wiki = WikipediaRetriever(top_k_results=3, doc_content_chars_max=4000)
        self._cache = {}

    def fetch(self, query):
        if query in self._cache:
            logging.info(f"Wikipedia cache hit for '{query}'")
            return self._cache[query]

        try:
            docs = self.wiki.invoke(query)
            
            if not docs:
                return []
                
            formatted_docs = []
            for doc in docs:
                title = doc.metadata.get("title", "Unknown Title")
                source = doc.metadata.get("source", "No URL")
                content = doc.page_content
                formatted_docs.append({
                    "title": title,
                    "source": source,
                    "content": content
                })
                
            self._cache[query] = formatted_docs
            return formatted_docs
            
        except Exception as e:
            logging.error(f"Error fetching from Wikipedia: {e}")
            return []
