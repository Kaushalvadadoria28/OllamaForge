import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")
VECTORSTORE_DIR = os.path.join(BASE_DIR, "vectorstores")


DEFAULT_MODEL = "llama3"
EMBED_TYPE = os.getenv("EMBED_TYPE", "ollama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text:latest")
FALLBACK_EMBED_TYPE = os.getenv("FALLBACK_EMBED_TYPE", "sentence-transformers")
FALLBACK_EMBED_MODEL = os.getenv("FALLBACK_EMBED_MODEL", "all-MiniLM-L6-v2")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
