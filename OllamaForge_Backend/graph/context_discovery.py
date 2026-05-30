"""
Context Discovery Node
═════════════════════════════════════════════════════════════════════
Runs BEFORE the supervisor to intelligently explore and gather context
from the workspace, documentation, and user intent. This prevents vague
"I need more info" responses by proactively discovering requirements.
"""

import os
from core.logger import setup_logger
from config import LOG_DIR

logger = setup_logger(LOG_DIR)


def discover_workspace_context(state: dict, config: dict) -> dict:
    """
    FIX: Pre-exploration node that gathers context BEFORE supervisor routes.
    
    This node:
      1. Searches workspace for relevant files (README, requirements, config, schema)
      2. Extracts key metadata (project type, tech stack, schema info)
      3. Analyzes the user's question to infer intent
      4. Enriches the state with discovered context
      
    Result: Supervisor gets rich context to make better routing decisions.
    """
    
    question = state.get("question", "").lower()
    context_clues = {}
    
    # ── 1. Detect question intent category ──
    intent_map = {
        "generate": ["generate", "write", "create", "code", "script", "function"],
        "explain": ["explain", "how does", "what is", "describe", "tell me about"],
        "fix": ["fix", "debug", "error", "not working", "issue", "bug"],
        "query": ["query", "search", "find", "retrieve", "get", "list"],
        "api_schema": ["api", "endpoint", "route", "schema", "database", "table"],
    }
    
    detected_intent = "general"
    for intent_type, keywords in intent_map.items():
        if any(kw in question for kw in keywords):
            detected_intent = intent_type
            break
    
    context_clues["detected_intent"] = detected_intent
    
    # ── 2. Scan workspace for key metadata files ──
    workspace_files = {}
    root_dir = "d:\\OB"
    
    key_files = {
        "README": ["README.md", "README.txt"],
        "REQUIREMENTS": ["requirements.txt", "poetry.lock", "Pipfile"],
        "CONFIG": ["config.py", ".env", "config.json"],
        "SCHEMA": ["schema.sql", "test_schema.sql", "models.py"],
        "API_DOCS": ["api_documentation.md", "api_documentation.md.resolved"],
    }
    
    for file_type, candidates in key_files.items():
        for candidate in candidates:
            full_path = os.path.join(root_dir, candidate)
            if os.path.exists(full_path):
                workspace_files[file_type] = full_path
                break
    
    context_clues["available_files"] = list(workspace_files.keys())
    
    # ── 3. Extract project tech stack from requirements.txt or config ──
    tech_stack = {
        "languages": ["python"],
        "frameworks": [],
        "tools": [],
    }
    
    if "REQUIREMENTS" in workspace_files:
        try:
            with open(workspace_files["REQUIREMENTS"], "r") as f:
                reqs_content = f.read().lower()
                
                # Detect frameworks
                if "flask" in reqs_content:
                    tech_stack["frameworks"].append("Flask")
                if "django" in reqs_content:
                    tech_stack["frameworks"].append("Django")
                if "langchain" in reqs_content:
                    tech_stack["frameworks"].append("LangChain")
                if "langgraph" in reqs_content:
                    tech_stack["frameworks"].append("LangGraph")
                if "sqlalchemy" in reqs_content:
                    tech_stack["frameworks"].append("SQLAlchemy")
                
                # Detect tools
                if "faiss" in reqs_content:
                    tech_stack["tools"].append("FAISS")
                if "ollama" in reqs_content:
                    tech_stack["tools"].append("Ollama")
                if "wikipedia" in reqs_content:
                    tech_stack["tools"].append("Wikipedia")
        except Exception as e:
            logger.error(f"Failed to read requirements: {e}")
    
    context_clues["tech_stack"] = tech_stack
    
    # ── 4. Extract schema info if present ──
    if "SCHEMA" in workspace_files:
        try:
            with open(workspace_files["SCHEMA"], "r") as f:
                schema_content = f.read()
                # Count table names (crude but effective)
                table_count = schema_content.count("CREATE TABLE")
                context_clues["database_tables"] = table_count
                context_clues["has_schema"] = True
        except Exception as e:
            logger.error(f"Failed to read schema: {e}")    
    # ── 5b. Check for uploaded .sql files in UPLOAD_DIR and workspace root ──
    try:
        from config import UPLOAD_DIR, BASE_DIR
        sql_files = []
        
        # Scan UPLOAD_DIR
        if os.path.exists(UPLOAD_DIR):
            sql_files.extend([f for f in os.listdir(UPLOAD_DIR) if f.endswith(".sql")])
        
        # Also scan workspace root for .sql files
        if os.path.exists(BASE_DIR):
            root_sql_files = [
                f for f in os.listdir(BASE_DIR) 
                if f.endswith(".sql") and os.path.isfile(os.path.join(BASE_DIR, f))
            ]
            sql_files.extend(root_sql_files)
        
        # Remove duplicates
        sql_files = list(set(sql_files))
        
        if sql_files:
            context_clues["uploaded_sql_files"] = sql_files
            
            # Try to analyze first .sql file for schema info
            # Prefer files from UPLOAD_DIR, fall back to root
            first_sql_path = None
            if os.path.exists(UPLOAD_DIR):
                candidates = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".sql")]
                if candidates:
                    first_sql_path = os.path.join(UPLOAD_DIR, candidates[0])
            
            if first_sql_path is None:
                root_candidates = [
                    f for f in os.listdir(BASE_DIR) 
                    if f.endswith(".sql") and os.path.isfile(os.path.join(BASE_DIR, f))
                ]
                if root_candidates:
                    first_sql_path = os.path.join(BASE_DIR, root_candidates[0])
            
            if first_sql_path and os.path.exists(first_sql_path):
                try:
                    with open(first_sql_path, "r", encoding="utf-8", errors="replace") as f:
                        sql_content = f.read()
                        table_count = sql_content.count("CREATE TABLE")
                        context_clues["uploaded_sql_table_count"] = table_count
                        context_clues["uploaded_sql_size"] = len(sql_content)
                        
                        # Store first 3000 chars of SQL for quick analysis
                        context_clues["uploaded_sql_preview"] = sql_content[:3000]
                        logger.info(f"Analyzed SQL file: {first_sql_path}, tables: {table_count}, size: {len(sql_content)}")
                except Exception as e:
                    logger.error(f"Failed to analyze SQL file {first_sql_path}: {e}")
    except Exception as e:
        logger.error(f"Failed to scan for SQL files: {e}")    
    # ── 5. Extract API endpoints from documentation ──
    if "API_DOCS" in workspace_files:
        try:
            with open(workspace_files["API_DOCS"], "r") as f:
                api_content = f.read()
                # Count endpoint patterns
                endpoint_count = api_content.count("/api/")
                context_clues["api_endpoints_count"] = endpoint_count
        except Exception as e:
            logger.error(f"Failed to read API docs: {e}")
    
    # ── 6. Analyze user question for specificity ──
    specificity_score = 0
    
    # High specificity indicators
    if any(kw in question for kw in ["rag", "database", "wikipedia", "website", "graph", "db"]):
        specificity_score += 20
    if any(kw in question for kw in ["function", "class", "method", "endpoint"]):
        specificity_score += 15
    if any(kw in question for kw in ["python", "sql", "javascript", "go", "rust"]):
        specificity_score += 10
    if any(kw in question for kw in ["table", "tables", "schema", "column", "columns", "database", "db"]):
        specificity_score += 20
    if any(lang in question for lang in tech_stack["frameworks"]):
        specificity_score += 10
    
    # Low specificity indicators
    if ("help" in question or "how" in question) and len(question) < 20:
        specificity_score -= 10
    if "?" in question and question.count("?") > 1:
        specificity_score -= 5
    
    context_clues["specificity_score"] = specificity_score
    context_clues["is_ambiguous"] = specificity_score < 30
    
    # ── 7. Build enriched context block for supervisor ──
    context_block = f"""
### DISCOVERED WORKSPACE CONTEXT
- Detected Intent: {detected_intent}
- Specificity Score: {specificity_score}/100
- Tech Stack: {', '.join(tech_stack['frameworks']) or 'Unknown'}
- Available Tools: {', '.join(tech_stack['tools']) or 'None'}
- Workspace Files: {', '.join(context_clues.get('available_files', [])) or 'None'}
- Database Tables: {context_clues.get('database_tables', 'Unknown')}
- API Endpoints: ~{context_clues.get('api_endpoints_count', 0)}
- Uploaded SQL Files: {', '.join(context_clues.get('uploaded_sql_files', [])) or 'None'}
"""
    
    state["_context_clues"] = context_clues
    state["_workspace_context"] = context_block
    
    logger.info(f"Context discovery complete for question: {question[:80]}")
    print(context_block)
    
    return state


def handle_ambiguous_query(state: dict, config: dict) -> dict:
    """
    FIX: If query is ambiguous, flag it for the supervisor to handle
    with intelligent follow-up questions or broader context gathering.
    
    This node analyzes specificity and stores clarification hints
    that the supervisor and synthesis node can use to generate
    targeted responses instead of vague ones.
    """
    context_clues = state.get("_context_clues", {})
    question = state.get("question", "")
    
    # ── Only flag ambiguous queries ──
    specificity = context_clues.get("specificity_score", 100)
    if specificity >= 30:
        # Question is specific enough; pass through
        return state
    
    intent = context_clues.get("detected_intent", "general")
    
    # ── Map clarification hints based on intent ──
    # These guide the supervisor and synthesis to ask better follow-ups
    clarification_hints = {
        "generate": {
            "suggested_questions": [
                "What type of code? (Function / Class / Endpoint / Config / Integration)",
                "Which framework/tech? (Flask / LangChain / SQLAlchemy / Custom Python)",
                "Any specific requirement? (e.g., async, error handling, logging)"
            ],
            "context": f"User wants to generate code. Tech stack available: {context_clues.get('tech_stack', {}).get('frameworks', [])}"
        },
        "query": {
            "suggested_questions": [
                "Query which data source? (Database / RAG Documents / API / Other)",
                "What's the specific data you need?",
                "Any filters or specific conditions?"
            ],
            "context": f"User wants to query data. Database has {context_clues.get('database_tables', 0)} tables. "
        },
        "fix": {
            "suggested_questions": [
                "Which component is failing? (RAG / Database / API / Agent)",
                "What error message are you seeing?",
                "What did you last change?"
            ],
            "context": "User is debugging an issue. "
        },
        "explain": {
            "suggested_questions": [
                "How much detail? (Quick summary / Medium / Detailed walkthrough)",
                "Focus on what aspect? (Architecture / Code / Configuration)",
                "Any specific component?"
            ],
            "context": "User wants an explanation. "
        },
    }
    
    hints = clarification_hints.get(intent, {
        "suggested_questions": [
            "What's your primary goal? (Generate / Explain / Fix / Query)",
            "What specific resource or component?",
            "Any constraints or preferences?"
        ],
        "context": "User query is ambiguous. "
    })
    
    # ── Store ambiguity metadata in state for supervisor/synthesis to use ──
    state["_clarification_needed"] = True
    state["_ambiguity_hints"] = hints
    state["_ambiguity_severity"] = "low" if specificity > 0 else "high"
    
    logger.info(
        f"Ambiguity detected: intent={intent}, specificity={specificity}/100. "
        f"Suggested clarifications will be applied during synthesis."
    )
    print(f"⚠️  Query specificity low ({specificity}/100). Using context hints to guide generation...")
    
    return state
