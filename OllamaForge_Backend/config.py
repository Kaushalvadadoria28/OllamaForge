import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOG_DIR = os.path.join(BASE_DIR, "logs")
VECTORSTORE_DIR = os.path.join(BASE_DIR, "vectorstores")


DEFAULT_MODEL = "llama3"
EMBED_MODEL = "nomic-embed-text:latest"
