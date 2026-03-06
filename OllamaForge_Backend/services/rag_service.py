import os
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

class RAGService:

    def __init__(self, session_id, vectorstore_dir):
        self.session_id = session_id
        self.vectorstore_path = os.path.join(vectorstore_dir, session_id)
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text:latest")
        self.vectorstore = None

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
            return False

        try:
            self.vectorstore = FAISS.load_local(
                self.vectorstore_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            return True
        except Exception:
            return False


    def retrieve(self, question):
        docs = self.vectorstore.similarity_search(question, k=4)
        return "\n\n".join([doc.page_content for doc in docs])



