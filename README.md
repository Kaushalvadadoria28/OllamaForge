# OllamaForge

OllamaForge is a powerful full-stack application designed to facilitate seamless interaction with local LLMs (Ollama) and structured data. It provides a robust backend for processing RAG (Retrieval-Augmented Generation) and a modern frontend for a premium user experience.

## 🚀 Features

- **Local LLM Integration**: Powered by Ollama for privacy and speed.
- **RAG Support**: Upload documents and chat with your data.
- **Structured Data Analysis**: Integration with SQLite databases for complex queries.
- **Modern UI**: Built with React, Vite, and Tailwind CSS for a sleek, responsive experience.
- **Extensible Architecture**: Modular design for easy customization of nodes and services.

## 🛠️ Tech Stack

### Backend

- **Python / FastAPI**: High-performance API layer.
- **LangGraph / LangChain**: Advanced orchestration for LLM workflows.
- **SQLite**: Local persistent storage.
- **FAISS**: Vector database for RAG.

### Frontend

- **React**: Component-based UI.
- **Vite**: Ultra-fast build tool.
- **Tailwind CSS / Shadcn UI**: For premium styling and components.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai/) installed and running.

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/Kaushalvadadoria28/OllamaForge.git
   cd OllamaForge
   ```

2. **Ollama Setup**:
   Ensure Ollama is running, then pull the required models:

   ```bash
   ollama pull llama3
   ollama pull nomic-embed-text
   ```

3. **Backend Setup**:

   ```bash
   cd OllamaForge_Backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```

4. **Frontend Setup**:

   ```bash
   cd ../OllamaForge_Frontend
   npm install
   npm run dev
   ```

## 📄 License

MIT License
