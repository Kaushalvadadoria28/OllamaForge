from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import time
import json
import sqlite3

from graph.graph_builder import build_graph
from services.rag_service import RAGService
from services.database_service import DatabaseService
from core.logger import setup_logger
from config import LOG_DIR, UPLOAD_DIR, VECTORSTORE_DIR
from core.graph_logger import log_graph_summary


from core.storage import (
    init_db,
    create_session,
    get_session,
    update_source,
    update_model,
    update_rag_path,
    update_db_path,
    save_message,
    get_messages
)
from services.wikipedia_service import WikipediaService

# --------------------------------------------------
# INITIALIZATION
# --------------------------------------------------

app = Flask(__name__)
CORS(app)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTORSTORE_DIR, exist_ok=True)


logger = setup_logger(LOG_DIR)
print(f"Backend initialized. Logs are being written to {LOG_DIR} and terminal.")
init_db()

# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "OllamaForge is running"})

# --------------------------------------------------
# SESSION MANAGEMENT
# --------------------------------------------------

@app.route("/api/init_session", methods=["POST"])
def init_session():
    data = request.get_json()
    session_id = data.get("session_id", f"session_{int(time.time())}")

    create_session(session_id)

    return jsonify({
        "status": "success",
        "session_id": session_id
    })


@app.route("/api/set_model", methods=["POST"])
def set_model():
    data = request.get_json()
    session_id = data.get("session_id")
    model = data.get("model")

    session = get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 400

    update_model(session_id, model)

    return jsonify({"status": "success"})


@app.route("/api/set_source", methods=["POST"])
def set_source():
    data = request.get_json()
    session_id = data.get("session_id")
    source = data.get("source")

    session = get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 400

    update_source(session_id, source)

    return jsonify({"status": "success"})

# --------------------------------------------------
# RAG UPLOAD ROUTES (STORE PATH ONLY)
# --------------------------------------------------

@app.route("/api/upload_pdf", methods=["POST"])
def upload_pdf():
    session_id = request.form.get("session_id")
    session = get_session(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 400

    file = request.files.get("file")
    path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(path)

    try:
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(path)
        pages = loader.load()
        content = "\n".join([p.page_content for p in pages])
    except Exception as e:
        return jsonify({"error": f"Failed to parse PDF: {e}"}), 500

    rag = RAGService(session_id, VECTORSTORE_DIR)
    rag.build_and_persist(content)

    update_rag_path(session_id, path)

    return jsonify({"status": "PDF processed & vectorstore persisted"}) 


@app.route("/api/upload_docx", methods=["POST"])
def upload_docx():
    session_id = request.form.get("session_id")

    session = get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(path)

    try:
        from langchain_community.document_loaders import Docx2txtLoader
        loader = Docx2txtLoader(path)
        pages = loader.load()
        content = "\n".join([p.page_content for p in pages])
    except Exception as e:
        return jsonify({"error": f"Failed to parse DOCX: {e}"}), 500

    rag = RAGService(session_id, VECTORSTORE_DIR)
    rag.build_and_persist(content)

    update_rag_path(session_id, path)

    return jsonify({"status": "DOCX processed & vectorstore persisted"}) 


@app.route("/api/upload_website", methods=["POST"])
def upload_website():
    data = request.get_json()
    session_id = data.get("session_id")
    url = data.get("url")

    session = get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 400

    update_rag_path(session_id, url)

    return jsonify({"status": "Website URL stored successfully"})

# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

import uuid

@app.route("/api/init_database", methods=["POST"])
def init_database():
    data = request.get_json()
    session_id = data.get("session_id")
    db_path = data.get("db_path", "").strip()

    session = get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 400

    if not db_path:
        return jsonify({"error": "No database path provided"}), 400

    # 1. Handle .sql script files
    if db_path.endswith(".sql"):
        if not os.path.exists(db_path):
            return jsonify({"error": "SQL file not found on server"}), 400
        
        # Create a new destination SQLite DB mapped to this session
        new_db_filename = f"parsed_{uuid.uuid4().hex[:8]}.db"
        new_db_path = os.path.join(UPLOAD_DIR, new_db_filename)

        try:
            with open(db_path, "r", encoding="utf-8", errors="replace") as f:
                raw_script = f.read()
            
            # Clean MySQL-specific dump files for SQLite ingest
            import re
            lines = []
            for line in raw_script.splitlines():
                clean_line = line.strip()
                # Skip MySQL specific comments and metadata
                if clean_line.startswith('/*!') or clean_line.startswith('--') or clean_line.upper().startswith('CREATE DATABASE') or clean_line.upper().startswith('USE ') or clean_line.startswith('LOCK') or clean_line.startswith('UNLOCK') or clean_line.upper().startswith('SET '):
                    continue
                
                # Handle MySQL ENGINE/COLLATE/AUTO_INCREMENT
                if 'ENGINE=InnoDB' in clean_line:
                    clean_line = re.sub(r'ENGINE=InnoDB.*?COLLATE=.*?ci;', ';', clean_line)
                    clean_line = re.sub(r'ENGINE=InnoDB.*?;', ';', clean_line)
                
                # Remove MySQL INDEX/KEY/PRIMARY KEY definitions that SQLite doesn't like inside CREATE TABLE if they use MySQL specific syntax
                # This is a bit aggressive but helps with basic dumps
                if clean_line.upper().startswith('KEY ') or clean_line.upper().startswith('UNIQUE KEY ') or clean_line.upper().startswith('PRIMARY KEY ('):
                    # Check if it's the last line (doesn't end with comma)
                    if not clean_line.endswith(','):
                        # We might need to handle the previous line's comma
                        # For now, let's just replace with a placeholder or skip if it's a simple index
                        continue
                    continue

                if clean_line:
                    lines.append(clean_line)
            
            clean_script = '\n'.join(lines)
            # Post-processing for trailing commas in CREATE TABLE blocks (very common after removing indices)
            clean_script = re.sub(r',\s*\n\)', '\n)', clean_script)
            clean_script = re.sub(r',\s*\)', '\)', clean_script)

            conn = sqlite3.connect(new_db_path)
            cursor = conn.cursor()
            cursor.executescript(clean_script)
            conn.commit()
            conn.close()

            db_path = f"sqlite:///{new_db_path}"

        except Exception as e:
            return jsonify({"error": f"Failed to parse and execute SQL file: {e}"}), 500

    # 2. Handle generic direct .db/.sqlite paths vs URIs
    elif db_path.endswith(".db") or db_path.endswith(".sqlite"):
        if not os.path.exists(db_path):
            return jsonify({"error": "Database file not found"}), 400
        db_path = f"sqlite:///{os.path.abspath(db_path)}"
        
    # else assume it is already a valid SQLAlchemy URI like postgresql://user:pass@localhost/db.

    update_db_path(session_id, db_path)

    return jsonify({"status": "Database path stored successfully", "db_uri": db_path})

# --------------------------------------------------
# MAIN CHAT ENDPOINT
# --------------------------------------------------

# @app.route("/api/chat", methods=["POST"])
# def chat():
#     data = request.get_json()
#     session_id = data.get("session_id")
#     message = data.get("message")
#     urls = data.get("urls") or data.get("url")
#     system_prompt = data.get("system_prompt", "")
#     temperature = data.get("temperature", 0.5)
#     stream_flag = data.get("stream", False)

#     session = get_session(session_id)
#     print("SESSION:", session)
#     if not session:
#         return jsonify({"error": "Session not found"}), 400

#     history = get_messages(session_id)

#     rag_service = None
#     db_service = None

#     # ---------- RAG ----------
#     if session["source"] == "RAG":

#         if not session.get("rag_path"):
#             return jsonify({"error": "No document uploaded for RAG mode"}), 400

#         rag_service = RAGService(session_id, VECTORSTORE_DIR)

#         if not rag_service.load():
#             return jsonify({
#                 "error": "Vectorstore missing. Please re-upload document."
#             }), 400

#     # ---------- DATABASE ----------
#     if session["source"] == "Database":
#         if not session.get("db_path"):
#             return jsonify({"error": "Database not initialized"}), 400

#         db_service = DatabaseService(session["db_path"])

#     # ---------- WEBSITE ----------
#     if session["source"] == "Website":
#         # Fallback to connected URL if none provided in request
#         if not urls and session.get("rag_path"):
#             urls = session["rag_path"]
            
#         # Initialize an empty RAGService just in case we hit an enormous website and need to chunk it.
#         rag_service = RAGService(session_id, VECTORSTORE_DIR)

#     graph = build_graph(
#         session["source"],
#         {
#             "model": session["model"],
#             "temperature": temperature,
#             "wikipedia": WikipediaService(),  # Wikipedia node doesn't require initialization
#             "rag": rag_service,
#             "db": db_service
#         }
#     )

#     start_time = time.time()
    
#     initial_state = {
#         "question": message,
#         "response": "",
#         "history": history,
#         "urls": urls,
#         "system_prompt": system_prompt,
#         "stream": stream_flag,
#         "next_action": "",
#         "tool_output": "",
#         "agent_scratchpad": ""
#     }

#     if stream_flag:
#         from flask import Response
#         def generate():
#             try:
#                 result = graph.invoke(initial_state)
#                 response_obj = result["response"]
                
#                 full_response = ""
                
#                 # If the response is a generator (streaming LLM)
#                 if hasattr(response_obj, '__iter__') and not isinstance(response_obj, (str, list, dict, set)):
#                     for chunk in response_obj:
#                         full_response += chunk
#                         data = json.dumps({"content": chunk})
#                         yield f"data: {data}\n\n"
#                 else:
#                     # If the response is a string (e.g. Database result or error)
#                     full_response = str(response_obj)
#                     data = json.dumps({"content": full_response})
#                     yield f"data: {data}\n\n"
                
#                 total_time = time.time() - start_time
#                 log_graph_summary(session_id, total_time)
#                 save_message(session_id, "user", message)
#                 save_message(session_id, "assistant", full_response)
#             except Exception as e:
#                 logger.error(f"Error in streaming generation: {str(e)}")
#                 data = json.dumps({"error": str(e)})
#                 yield f"data: {data}\n\n"
            
#         return Response(generate(), mimetype="text/event-stream")
        
#     else:
#         # Standard Synchronous Generation
#         try:
#             result = graph.invoke(initial_state)
#             total_time = time.time() - start_time
#             log_graph_summary(session_id, total_time)
#             response = result["response"]
#             save_message(session_id, "user", message)
#             save_message(session_id, "assistant", response)
#             return jsonify({"response": response})
#         except Exception as e:
#             logger.error(f"Error in chat endpoint: {str(e)}")
#             return jsonify({"error": f"Failed to generate response: {str(e)}"}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    session_id = data.get("session_id")
    message = data.get("message")
    urls = data.get("urls") or data.get("url")
    system_prompt = data.get("system_prompt", "")
    temperature = data.get("temperature", 0.5)
    stream_flag = data.get("stream", False)

    session = get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 400

    history = get_messages(session_id)

    # Instantiate ALL initialized services to make them available to the Agentic runtime environment
    rag_service = None
    rag_path = session.get("rag_path")
    if rag_path:
        rag_service = RAGService(session_id, VECTORSTORE_DIR)
        if not rag_service.load():
            logger.warning(
                f"Session {session_id}: RAG vectorstore failed to load. Path={rag_path}."
            )
            if session.get("source") == "RAG":
                error_msg = (
                    "RAG document database could not be loaded. "
                    "Please re-upload the file or rebuild the vectorstore."
                )
                return jsonify({"error": error_msg}), 500
            rag_service = None
    elif session.get("source") == "RAG":
        return jsonify({"error": "No document uploaded for RAG mode. Please upload a PDF or DOCX first."}), 400

    db_service = None
    if session.get("db_path"):
        db_path = session.get("db_path", "").strip()
        
        # ── Handle .sql files that haven't been processed yet ──
        if db_path.endswith(".sql"):
            logger.info(
                f"Session {session_id}: SQL file uploaded but not yet processed into a database. "
                f"File: {db_path}. User needs to call /api/init_database to convert it."
            )
            if session.get("source") == "Database":
                return jsonify({
                    "error": "SQL file detected but not yet processed into a database. "
                             "Please call the /api/init_database endpoint with the SQL file path first."
                }), 400
            # If source is not Database, skip database initialization
            db_service = None
        
        # ── Validate that db_path is a proper SQLAlchemy URI ──
        elif not db_path or not (db_path.startswith("sqlite://") or "://" in db_path):
            logger.warning(
                f"Session {session_id}: Invalid database URI format. Path={db_path}."
            )
            if session.get("source") == "Database":
                return jsonify({"error": "Database URI is invalid or not initialized properly."}), 400
            # If source is not Database, db_service remains None
        else:
            try:
                db_service = DatabaseService(db_path)
            except Exception as db_err:
                logger.warning(
                    f"Session {session_id}: Failed to initialize database service. Error: {db_err}"
                )
                if session.get("source") == "Database":
                    return jsonify({"error": f"Database connection failed: {str(db_err)}"}), 500
                db_service = None
    elif session.get("source") == "Database":
        return jsonify({"error": "Database not initialized. Please set up a database connection first."}), 400

    # Build dynamic multi-tool contextual environment mapping configurations
    graph_config = {
        "model": session["model"],
        "session_id": session_id,
        "temperature": temperature,
        "wikipedia": WikipediaService(),
        "rag": rag_service,
        "db": db_service
    }

    graph = build_graph(session["source"], graph_config)
    start_time = time.time()
    
    # Fully initialize core properties to avoid graph mutation KeyError bugs
    initial_state = {
        "question": message,
        "response": "",
        "history": history,
        "urls": urls,
        "system_prompt": system_prompt,
        "stream": stream_flag,
        "temperature": temperature,
        "next_action": "",
        "tool_output": "",
        "agent_scratchpad": "",
        # Context discovery fields (initialized empty; populated by discover_context node)
        "_context_clues": {},
        "_workspace_context": "",
        "_clarification_needed": False,
        "_clarification_questions": [],
    }

    if stream_flag:
        def generate():
            try:
                result = graph.invoke(initial_state)
                response_obj = result["response"]
                full_response = ""
                
                if hasattr(response_obj, '__iter__') and not isinstance(response_obj, (str, list, dict, set)):
                    for chunk in response_obj:
                        full_response += chunk
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
                else:
                    full_response = str(response_obj)
                    yield f"data: {json.dumps({'content': full_response})}\n\n"
                
                log_graph_summary(session_id, time.time() - start_time)
                save_message(session_id, "user", message)
                save_message(session_id, "assistant", full_response)
            except Exception as e:
                logger.error(f"Error in streaming generation: {str(e)}")
                error_msg = str(e)
                if "429" in error_msg and ("quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower()):
                    error_msg = "API Quota Exceeded: You have reached the rate limit or quota for the Gemini API. Please check your Google AI billing and plan."
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
            
        return Response(generate(), mimetype="text/event-stream")
        
    else:
        try:
            result = graph.invoke(initial_state)
            response = result["response"]
            log_graph_summary(session_id, time.time() - start_time)
            save_message(session_id, "user", message)
            save_message(session_id, "assistant", response)
            return jsonify({"response": response})
        except Exception as e:
            logger.error(f"Error in chat endpoint: {str(e)}")
            error_msg = str(e)
            if "429" in error_msg and ("quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower()):
                error_msg = "API Quota Exceeded: You have reached the rate limit or quota for the Gemini API. Please check your Google AI billing and plan."
            return jsonify({"error": error_msg}), 500

# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)




