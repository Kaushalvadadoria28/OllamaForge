import os
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from config import EMBED_TYPE, EMBED_MODEL, FALLBACK_EMBED_TYPE, FALLBACK_EMBED_MODEL

class EmbeddingWithFallback(Embeddings):
    """Wrapper that provides automatic fallback from primary to secondary embedding provider."""
    
    def __init__(self, primary, fallback_factory=None):
        super().__init__()
        self.primary = primary
        self.fallback_factory = fallback_factory
        self._fallback = None

    def _get_fallback(self):
        if self._fallback is None and self.fallback_factory is not None:
            self._fallback = self.fallback_factory()
        return self._fallback

    def embed_documents(self, texts):
        try:
            return self.primary.embed_documents(texts)
        except Exception as exc:
            fallback = self._get_fallback()
            if fallback is None:
                raise
            print(f"Primary embedding failed: {exc}. Falling back to secondary embeddings.")
            return fallback.embed_documents(texts)

    def embed_query(self, text):
        try:
            return self.primary.embed_query(text)
        except Exception as exc:
            fallback = self._get_fallback()
            if fallback is None:
                raise
            print(f"Primary embedding query failed: {exc}. Falling back to secondary embeddings.")
            return fallback.embed_query(text)

    def aembed_documents(self, texts):
        if hasattr(self.primary, "aembed_documents"):
            try:
                return self.primary.aembed_documents(texts)
            except Exception as exc:
                fallback = self._get_fallback()
                if fallback is None or not hasattr(fallback, "aembed_documents"):
                    raise
                print(f"Primary async embedding failed: {exc}. Falling back to secondary embeddings.")
                return fallback.aembed_documents(texts)
        fallback = self._get_fallback()
        if fallback is None or not hasattr(fallback, "aembed_documents"):
            raise AttributeError("No async embedding method available for primary or fallback embeddings.")
        return fallback.aembed_documents(texts)


class RAGService:

    def __init__(self, session_id, vectorstore_dir):
        self.session_id = session_id
        self.vectorstore_path = os.path.join(vectorstore_dir, session_id)
        self.embeddings = self._create_embeddings()
        self.vectorstore = None
        self.load_error = None

    def _create_embeddings(self):
        primary = None
        try:
            primary = self._create_embeddings_for_type(EMBED_TYPE, EMBED_MODEL)
        except Exception as exc:
            if FALLBACK_EMBED_TYPE:
                print(
                    f"Primary embedding type '{EMBED_TYPE}' failed to initialize: {exc}. "
                    f"Falling back to '{FALLBACK_EMBED_TYPE}'..."
                )
                return self._create_embeddings_for_type(FALLBACK_EMBED_TYPE, FALLBACK_EMBED_MODEL)
            raise RuntimeError(
                f"Failed to initialize embeddings for type '{EMBED_TYPE}'. "
                f"Set FALLBACK_EMBED_TYPE and FALLBACK_EMBED_MODEL in config or env to try a second embedding provider. Original error: {exc}"
            ) from exc

        if FALLBACK_EMBED_TYPE:
            return EmbeddingWithFallback(
                primary,
                fallback_factory=lambda: self._create_embeddings_for_type(FALLBACK_EMBED_TYPE, FALLBACK_EMBED_MODEL),
            )

        return primary

    def _create_embeddings_for_type(self, embed_type, model_name):
        embed_type = str(embed_type or "").strip().lower()
        if embed_type in {"ollama", "langchain_ollama"}:
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError as exc:
                raise RuntimeError("Ollama embeddings package is not installed.") from exc
            return OllamaEmbeddings(model=model_name)

        if embed_type in {"sentence-transformers", "sentence_transformers", "st"}:
            return self._create_sentence_transformers_embeddings(model_name)

        raise ValueError(
            f"Unsupported embedding type '{embed_type}'. Supported types: ollama, sentence-transformers."
        )

    def _create_sentence_transformers_embeddings(self, model_name):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install it with 'pip install sentence-transformers'."
            ) from exc

        class SentenceTransformersWrapper(Embeddings):
            def __init__(self, model_name):
                super().__init__()
                self.model = SentenceTransformer(model_name)

            def embed_documents(self, texts):
                embeddings = self.model.encode(texts, convert_to_numpy=True)
                return embeddings.tolist()

            def embed_query(self, text):
                embedding = self.model.encode([text], convert_to_numpy=True)
                return embedding[0].tolist()

        return SentenceTransformersWrapper(model_name)

    def build_and_persist(self, content):
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        chunks = splitter.split_text(content)

        self.vectorstore = FAISS.from_texts(
            chunks,
            self.embeddings
        )

        os.makedirs(self.vectorstore_path, exist_ok=True)

        self.vectorstore.save_local(self.vectorstore_path)

    def load(self):
        print("Loading from:", self.vectorstore_path)
        print("Exists:", os.path.exists(self.vectorstore_path))
        if not os.path.exists(self.vectorstore_path):
            self.load_error = f"Vectorstore path not found: {self.vectorstore_path}"
            print(self.load_error)
            return False

        try:
            self.vectorstore = FAISS.load_local(
                self.vectorstore_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            return True
        except Exception as exc:
            self.load_error = f"Failed to load vectorstore: {exc}"
            print(self.load_error)
            return False


    def retrieve(self, question):
        if self.vectorstore is None:
            raise RuntimeError("Vectorstore is not loaded. Cannot retrieve document context.")
        docs = self.vectorstore.similarity_search(question, k=4)
        return "\n\n".join([doc.page_content for doc in docs])



