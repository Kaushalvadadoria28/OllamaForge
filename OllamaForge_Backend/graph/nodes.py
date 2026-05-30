from services.llm_service import LLMService
from services.wikipedia_service import WikipediaService
from services.website_service import WebsiteService
import time
import re
import concurrent.futures
from core.graph_logger import log_node_execution
from core.token_utils import estimate_tokens


# ═══════════════════════════════════════════════════════════════════
# MONITORING DECORATOR
# ═══════════════════════════════════════════════════════════════════

def monitored_node(node_name):
    def decorator(func):
        def wrapper(state, config):
            start_time = time.time()
            input_text = state.get("question", "")
            result = func(state, config)
            execution_time = time.time() - start_time
            output_text = (
                result.get("response", "")
                if result.get("response")
                else result.get("tool_output", "")
            )

            if hasattr(output_text, "__iter__") and not isinstance(
                output_text, (str, list, dict, set)
            ):
                token_usage = estimate_tokens(input_text)
                log_output = "<Streamed Response>"
            else:
                token_usage = estimate_tokens(input_text) + estimate_tokens(str(output_text))
                log_output = str(output_text)

            # Safe session_id extraction for both plain dict config and LangGraph RunnableConfig
            session_id = (
                config.get("session_id")
                if isinstance(config, dict)
                else config.get("configurable", {}).get("session_id")
            )

            log_node_execution(
                session_id=session_id,
                node_name=node_name,
                input_data=input_text,
                output_data=log_output,
                execution_time=execution_time,
                token_usage=token_usage,
            )
            return result

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════
# HELPER: TIMEOUT-GUARDED LLM INVOKE
# ═══════════════════════════════════════════════════════════════════

def _invoke_with_timeout(llm, prompt, timeout_seconds=30):
    """
    Wraps llm.invoke() in a thread executor with a hard timeout.
    Raises concurrent.futures.TimeoutError if the LLM does not
    respond within timeout_seconds.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(llm.invoke, prompt)
        return future.result(timeout=timeout_seconds)


# ═══════════════════════════════════════════════════════════════════
# HELPER: BUILD DYNAMIC CAPABILITY STATUS BLOCK
# ═══════════════════════════════════════════════════════════════════

def _build_capability_status(config: dict) -> str:
    """
    Generates a real-time status block showing the supervisor
    exactly which tools are initialised and available for this session.
    """
    lines = []

    if config.get("rag"):
        lines.append("  ✅ RAG   : An uploaded document IS available. For any document-specific question, use 'rag' FIRST.")
    else:
        lines.append("  ❌ RAG   : No document has been uploaded. Do NOT choose 'rag'.")

    if config.get("db"):
        lines.append("  ✅ DB    : A database connection is active. Use 'db' for data/table queries.")
    else:
        lines.append("  ❌ DB    : No database connected. Do NOT choose 'db'.")

    if config.get("wikipedia"):
        lines.append("  ✅ WIKI  : Wikipedia is available for general knowledge lookups.")
    else:
        lines.append("  ❌ WIKI  : Wikipedia service is unavailable. Do NOT choose 'wiki'.")

    lines.append("  ✅ WEB   : Website scraping is always available if a URL is provided.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# NODE: SUPERVISOR ROUTER
# ═══════════════════════════════════════════════════════════════════

@monitored_node("supervisor_router")
def supervisor_router_node(state: dict, config: dict) -> dict:
    llm = LLMService(config["model"], temperature=0.1)

    scratchpad = state.get("agent_scratchpad", "")
    tool_output = state.get("tool_output", "")

    # Append the latest tool observation into the scratchpad
    # BEFORE calling the LLM so the supervisor sees it in this same cycle.
    if tool_output:
        scratchpad += f"\n[Observation]: {tool_output}\n"
        state["tool_output"] = ""

    # Always persist updated scratchpad before any LLM call
    state["agent_scratchpad"] = scratchpad

    print(f"--- SUPERVISOR CALLED ---")
    print(f"Scratchpad length  : {len(scratchpad)}")

    # Count real tool invocations (Observations), not Thoughts
    MAX_TOOL_CALLS = 4
    tool_call_count = scratchpad.count("[Observation]")
    print(f"Tool call count    : {tool_call_count}")

    # Use the source hint on the first decision when available and valid
    source_hint = config.get("_source_hint", "")
    if source_hint and not scratchpad and source_hint in {"rag", "db", "wiki", "web"}:
        if config.get(source_hint):
            print(f"Supervisor source hint active: {source_hint}")
            state["next_action"] = source_hint
            state["agent_scratchpad"] = (
                scratchpad
                + f"\n[Thought]: Starting with preferred source '{source_hint}'."
            )
            return state

    # Minimum-evidence check before guardrail forces complete
    EVIDENCE_KEYWORDS = [
        "Retrieved Context",
        "Wikipedia Context Found",
        "SQL Output Raw Data",
        "Website Direct Scraped",
        "Website Vector Chunk",
    ]
    has_useful_data = any(kw in scratchpad for kw in EVIDENCE_KEYWORDS)

    if tool_call_count >= MAX_TOOL_CALLS:
        # If we still have no evidence and RAG is available, force one RAG call
        if not has_useful_data and config.get("rag"):
            print(">>> GUARDRAIL: No evidence yet — forcing RAG before completing <<<")
            state["next_action"] = "rag"
            state["agent_scratchpad"] = (
                scratchpad
                + "\n[Thought]: Guardrail override — forcing RAG retrieval before final synthesis."
            )
            return state

        print(">>> GUARDRAIL ACTIVATED: FORCING COMPLETE <<<")
        state["next_action"] = "complete"
        state["agent_scratchpad"] = (
            scratchpad
            + "\n[Thought]: Maximum tool calls reached. Synthesizing from all gathered data."
        )
        return state

    # Dynamic capability status injected into the prompt
    capability_status = _build_capability_status(config)

    # Include discovered workspace context in supervisor prompt
    workspace_context = state.get("_workspace_context", "")
    
    # ── NEW: Include SQL file preview if available ──
    sql_file_context = ""
    context_clues = state.get("_context_clues", {})
    if context_clues.get("uploaded_sql_files"):
        sql_files = context_clues.get("uploaded_sql_files", [])
        table_count = context_clues.get("uploaded_sql_table_count", 0)
        sql_size = context_clues.get("uploaded_sql_size", 0)
        sql_file_context = f"\n**Uploaded SQL Files Available:**\n- Files: {', '.join(sql_files)}\n- Tables: {table_count}\n- Size: {sql_size} bytes"

    router_prompt = f"""### TASK: Autonomous Action Routing
You are an orchestrator leading an agentic workflow. Accurately answer the user's question
by choosing the best available tool for the next step.

### DISCOVERED WORKSPACE INTELLIGENCE
{workspace_context}{sql_file_context}

### SESSION CAPABILITY STATUS — READ THIS BEFORE DECIDING:
{capability_status}

### ROUTING RULES (in priority order):
1. CRITICAL: DO NOT REPEAT actions. If the Scratchpad already contains a [Observation] from a tool, DO NOT choose that tool again.
2. If RAG ✅ and the question is about an uploaded document → choose 'rag'. (Skip if 'rag' was already used).
3. If DB ✅ and the question asks about data tables or database metrics → choose 'db'.
4. If WIKI ✅ and the question needs broad factual / encyclopedic knowledge → choose 'wiki'.
5. If a URL is present in the question and WEB is needed → choose 'web'.
6. If the Scratchpad contains enough data to answer, OR if you need a full document summary and already pulled RAG chunks → choose 'complete'.
7. If a tool returned an error or empty result → try a DIFFERENT available tool.

### CURRENT WORKING MEMORY (SCRATCHPAD):
{scratchpad if scratchpad else "No actions taken yet."}

### ORIGINAL USER QUESTION:
{state['question']}

### RESPONSE FORMAT:
Reply with exactly ONE word from this list: rag | db | wiki | web | complete
No punctuation, no markdown, no explanation.

### NEXT ACTION:"""

    try:
        decision = _invoke_with_timeout(llm, router_prompt, timeout_seconds=30)
        decision = decision.strip().lower().replace("`", "").replace("'", "").strip()

        valid_actions = ["rag", "db", "wiki", "web", "complete"]

        # Unknown action guard
        if decision not in valid_actions:
            decision = "complete"
        
        if f"Routing to '{decision}'" in scratchpad and decision != "complete":
            print(f">>> Hard Override: LLM tried to loop '{decision}'. Forcing 'complete'.")
            decision = "complete"

        # Extra safety: if supervisor picks an unavailable tool, override it
        if decision == "rag" and not config.get("rag"):
            decision = "wiki" if config.get("wikipedia") else "complete"
        if decision == "db" and not config.get("db"):
            decision = "wiki" if config.get("wikipedia") else "complete"
        if decision == "wiki" and not config.get("wikipedia"):
            decision = "rag" if config.get("rag") else "complete"

        state["next_action"] = decision
        state["agent_scratchpad"] = (
            scratchpad + f"\n[Thought]: Routing to '{decision}' engine."
        )
        print(f"Supervisor decision: {decision}")

    except concurrent.futures.TimeoutError:
        state["next_action"] = "complete"
        state["tool_output"] = "Supervisor timed out. Proceeding to synthesize with available data."
    except Exception as e:
        state["next_action"] = "complete"
        state["tool_output"] = f"Supervisor Error: {str(e)}"

    return state


# ═══════════════════════════════════════════════════════════════════
# NODE: WIKIPEDIA
# ═══════════════════════════════════════════════════════════════════

@monitored_node("wikipedia")
def wikipedia_node(state, config):
    if not config.get("wikipedia"):
        state["tool_output"] = (
            "Wikipedia service is unavailable. Try a different tool."
        )
        return state

    wiki = config["wikipedia"]
    llm = LLMService(config["model"])

    extraction_prompt = f"""### TASK: Wikipedia Search Query Extraction
Extract exactly 1 to 2 short keyword search terms from the question.
Output ONLY a comma-separated list of search terms. No explanation or quotes.
User Question: {state['question']}
OUTPUT:"""

    try:
        extracted_str = _invoke_with_timeout(llm, extraction_prompt, timeout_seconds=20)
        queries = [q.strip() for q in extracted_str.split(",") if q.strip()]
        if not queries:
            queries = [state["question"]]

        all_context = []
        for q in queries:
            try:
                docs = wiki.fetch(q)
                for d in docs:
                    all_context.append(f"Title: {d['title']} - Content: {d['content']}")
            except Exception as fetch_err:
                print(f"Wikipedia fetch failed for query '{q}': {fetch_err}")
                continue

        if not all_context:
            state["tool_output"] = (
                "Wikipedia search returned no results for this question. "
                "Try a different tool."
            )
        else:
            budget_per_result = max(500, 3000 // len(all_context))
            trimmed_context = []
            for chunk in all_context:
                if len(chunk) > budget_per_result:
                    chunk = chunk[:budget_per_result] + "...[Truncated]"
                trimmed_context.append(chunk)

            state["tool_output"] = "Wikipedia Context Found:\n" + "\n".join(trimmed_context)

    except concurrent.futures.TimeoutError:
        state["tool_output"] = "Wikipedia tool timed out. Try a different tool."
    except Exception as e:
        state["tool_output"] = (
            f"Wikipedia Tool Failure: {str(e)}. Try a different tool."
        )

    return state


# ═══════════════════════════════════════════════════════════════════
# NODE: RAG
# ═══════════════════════════════════════════════════════════════════

@monitored_node("rag")
def rag_node(state, config):
    if not config.get("rag"):
        state["tool_output"] = (
            "RAG Document service not initialized — no file has been uploaded. "
            "Try a different tool."
        )
        return state

    rag_service = config["rag"]
    try:
        context = rag_service.retrieve(state["question"])
        if not context or not str(context).strip():
            state["tool_output"] = (
                "RAG retrieval returned empty context for this question. "
                "The document may not contain relevant information. Try a different tool."
            )
        else:
            state["tool_output"] = f"Retrieved Context from Uploaded Document:\n{context}"
    except Exception as e:
        state["tool_output"] = f"RAG Tool Failure: {str(e)}. Try a different tool."
    return state


# ═══════════════════════════════════════════════════════════════════
# NODE: WEBSITE
# ═══════════════════════════════════════════════════════════════════

@monitored_node("website")
def website_node(state, config):
    import re
    urls = state.get("urls") or state.get("url")
    rag_service = config.get("rag")

    if not urls:
        question_text = state.get("question", "")
        extracted_urls = re.findall(r'(https?://[^\s]+)', question_text)
        if extracted_urls:
            urls = extracted_urls

    if not urls:
        state["tool_output"] = (
            "No URL addresses were provided for web scraping. Try a different tool."
        )
        return state

    try:
        web_service = WebsiteService()
        result = web_service.fetch(urls, rag_service)

        if result["type"] == "error":
            state["tool_output"] = (
                f"Website scraping failed: {result['content']}. Try a different tool."
            )
        elif result["type"] == "rag" and rag_service:
            context = rag_service.retrieve(state["question"])
            state["tool_output"] = f"Website Vector Chunk Context:\n{context}"
        else:
            state["tool_output"] = f"Website Direct Scraped Text Content:\n{result['content']}"
    except Exception as e:
        state["tool_output"] = f"Website Tool Failure: {str(e)}. Try a different tool."
    return state


# ═══════════════════════════════════════════════════════════════════
# NODE: DATABASE
# ═══════════════════════════════════════════════════════════════════

@monitored_node("database")
def database_node(state, config):
    if not config.get("db"):
        state["tool_output"] = (
            "Database connection service is uninitialized. Try a different tool."
        )
        return state

    db_service = config["db"]
    llm = LLMService(config["model"])
    schema_info = db_service.get_schema()
    dialect = db_service.get_dialect()

    dialect_rules = {
        "sqlite":     "- Use only SQLite syntax. For schema info, query sqlite_master table.",
        "mysql":      "- Use MySQL backticks for safe queries. Show tables via SHOW TABLES;",
        "postgresql": "- Use clean PostgreSQL public schema table identifiers.",
    }
    dialect_specific = dialect_rules.get(dialect.lower(), f"- Use valid {dialect} syntax.")

    sql_gen_prompt = f"""### TASK: Natural Language to SQL
Convert the user query into a valid single executable {dialect} SQL query.

### SCHEMA
{schema_info}

### DIRECTIONS
{dialect_specific}
- Output ONLY raw SQL code. No markdown boxes, no explanations.
- Append LIMIT 50 to prevent overflow.

Question: {state['question']}
SQL QUERY:"""

    raw_response = ""
    clean_sql = ""

    def _generate_sql(prompt):
        raw = _invoke_with_timeout(llm, prompt, timeout_seconds=30).strip()
        if "```" in raw:
            match = re.search(r"```sql(.*?)```", raw, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else raw.replace("```", "").strip()
        return raw

    try:
        # ── SQLite-specific schema helper ──
        if dialect.lower() == "sqlite" and re.search(r"\b(table|tables|schema|columns|column|describe|list|show)\b", state["question"], re.IGNORECASE):
            clean_sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        else:
            raw_response = _generate_sql(sql_gen_prompt)
            clean_sql = raw_response

        last_error = None
        for attempt in range(2):
            try:
                sql_result = db_service.execute(clean_sql)
                state["tool_output"] = (
                    f"Executed SQL Query: {clean_sql}\nSQL Output Raw Data: {sql_result}"
                )
                return state
            except Exception as exec_err:
                last_error = exec_err
                if attempt == 0:
                    print(f"SQL attempt 1 failed: {exec_err}. Auto-correcting...")
                    if dialect.lower() == "sqlite" and "sqlite_master" not in clean_sql:
                        clean_sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
                    else:
                        fix_prompt = f"""### TASK: SQL Error Correction
The following SQL query failed. Rewrite it to fix the problem.

### ORIGINAL QUERY:
{clean_sql}

### ERROR MESSAGE:
{str(exec_err)}

### SCHEMA:
{schema_info}

Output ONLY the corrected raw SQL. No markdown, no explanation.
CORRECTED SQL:"""
                        try:
                            clean_sql = _generate_sql(fix_prompt)
                        except Exception:
                            break

        state["tool_output"] = (
            f"Database Tool Failed after auto-correction. "
            f"Last query: {clean_sql}\nError: {str(last_error)}. "
            "Try a different tool."
        )

    except concurrent.futures.TimeoutError:
        state["tool_output"] = "Database SQL generation timed out. Try a different tool."
    except Exception as e:
        state["tool_output"] = (
            f"Database Tool Exception: {str(e)} on query: {raw_response}. "
            "Try a different tool."
        )

    return state


# ═══════════════════════════════════════════════════════════════════
# HELPER: GENERATE NEXT-STEP SUGGESTIONS
# ═══════════════════════════════════════════════════════════════════

def _generate_suggestions(llm, question: str, answer: str, config: dict) -> str:
    """
    Calls the LLM to generate 3 contextual follow-up suggestions based on
    the question that was just answered and the tools available in the session.
    Returns a formatted markdown block ready to append to the final response.
    """
    available = []
    if config.get("rag"):
        available.append("uploaded document (RAG)")
    if config.get("db"):
        available.append("database queries")
    if config.get("wikipedia"):
        available.append("Wikipedia")
    available.append("website scraping")

    available_str = ", ".join(available)

    suggestions_prompt = f"""### TASK: Generate Follow-Up Suggestions
Based on the user's question and the answer just given, suggest exactly 3 concise,
actionable follow-up questions the user could ask next.

The system has these capabilities available: {available_str}.
Tailor suggestions to what can realistically be answered using these capabilities.

### USER'S ORIGINAL QUESTION:
{question}

### ANSWER JUST PROVIDED (summary):
{answer[:800]}

### RULES:
- Output ONLY a valid JSON array of exactly 3 short question strings.
- Each question must be under 15 words.
- Do not include numbering, bullet points, markdown, or any text outside the JSON array.
- Format exactly like this: ["Question one?", "Question two?", "Question three?"]

### OUTPUT:"""

    try:
        raw = _invoke_with_timeout(llm, suggestions_prompt, timeout_seconds=20)
        # Extract JSON array from the response
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            import json
            suggestions = json.loads(match.group())
            if isinstance(suggestions, list) and len(suggestions) >= 1:
                lines = "\n".join(f"- {s}" for s in suggestions[:3])
                return f"\n\n---\n**💡 You could ask next:**\n{lines}"
    except Exception as e:
        print(f"Suggestions generation failed (non-critical): {e}")

    return ""  # Graceful fallback — answer is still returned without suggestions


# ═══════════════════════════════════════════════════════════════════
# NODE: FINAL SYNTHESIS
# ═══════════════════════════════════════════════════════════════════

@monitored_node("final_synthesis")
def final_synthesis_node(state: dict, config: dict) -> dict:
    llm = LLMService(config["model"], temperature=state.get("temperature", 0.5))

    scratchpad = state.get("agent_scratchpad", "")
    
    # Include ambiguity hints from context discovery
    ambiguity_hints = state.get("_ambiguity_hints", {})
    clarification_context = ""
    if state.get("_clarification_needed"):
        hints = ambiguity_hints.get("suggested_questions", [])
        if hints:
            clarification_context = (
                "\n\n**NOTE: The original user query was somewhat ambiguous. "
                "Consider addressing these perspectives in your response:**\n"
                + "\n".join(f"- {h}" for h in hints[:2])
            )    
    # ── NEW: Include uploaded SQL file info for file info questions ──
    context_clues = state.get("_context_clues", {})
    sql_file_context = ""
    if context_clues.get("uploaded_sql_files"):
        sql_preview = context_clues.get("uploaded_sql_preview", "")
        sql_files = context_clues.get("uploaded_sql_files", [])
        sql_table_count = context_clues.get("uploaded_sql_table_count", 0)
        sql_size = context_clues.get("uploaded_sql_size", 0)
        
        sql_file_context = f"""

### UPLOADED SQL FILE INFORMATION (available for analysis):
**Files:** {', '.join(sql_files)}
**Tables:** {sql_table_count}
**Size:** {sql_size} bytes

**Preview (first 2000 chars):**
```sql
{sql_preview}
```
"""
    # Evidence gate: detect whether any tool returned real data
    EVIDENCE_KEYWORDS = [
        "Retrieved Context",
        "Wikipedia Context Found",
        "SQL Output Raw Data",
        "Website Direct Scraped",
        "Website Vector Chunk",
    ]
    has_real_data = any(kw in scratchpad for kw in EVIDENCE_KEYWORDS)

    # Include last 6 messages of conversation history for continuity
    history = state.get("history", [])
    history_text = ""
    if history:
        formatted = [
            f"{'User' if h.get('role') == 'user' else 'Assistant'}: {h.get('content', '')}"
            for h in history[-6:]
        ]
        history_text = "\n".join(formatted)

    # No-evidence path: give an honest answer instead of a hallucinated one
    if not has_real_data:
        no_data_prompt = f"""### TASK: Honest Failure Summary OR File Analysis
You are a helpful AI assistant. If tools didn't return data, give an honest explanation.
However, if the user is asking about an uploaded SQL file, provide analysis of that file instead.

### WHAT WAS ATTEMPTED:
{scratchpad if scratchpad else "No tools were successfully invoked."}

### USER'S QUESTION:
{state['question']}{sql_file_context}

### INSTRUCTIONS:
1. If SQL file info is provided and question is about it, analyze and describe the SQL file structure.
2. Otherwise, be honest that the information could not be retrieved this time.
3. Briefly explain what was tried (without exposing raw errors or stack traces).
4. Suggest 1-2 concrete things the user could do to get a better result
   (e.g. rephrase the question, upload a specific document, provide a URL).
5. Keep the tone warm and professional.

### RESPONSE:"""

        try:
            honest_answer = _invoke_with_timeout(llm, no_data_prompt, timeout_seconds=45)
        except concurrent.futures.TimeoutError:
            honest_answer = (
                "I was unable to retrieve relevant information for your question this time. "
                "Please try rephrasing, uploading a relevant document, or providing a direct URL."
            )
        except Exception as e:
            honest_answer = f"Unable to generate a response: {str(e)}"

        # Still append suggestions even on failure path
        suggestions_block = _generate_suggestions(llm, state["question"], honest_answer, config)
        state["response"] = honest_answer + suggestions_block
        return state

    # ── Normal synthesis path (evidence exists) ─────────────────────
    synthesis_prompt = f"""### TASK: Final Informational Synthesis
You are a polished data consultant. Review the execution trace scratchpad containing
all tool results, then write a comprehensive, professional final answer.

### PRIOR CONVERSATION CONTEXT:
{history_text if history_text else "No prior conversation history."}

### ACTIONS & TOOL RESULTS RECORD:
{scratchpad}

### ORIGINAL USER QUESTION:
{state['question']}{sql_file_context}

### INSTRUCTIONS:
1. Write a professional markdown-formatted response that directly answers the question.
2. Use only the data returned by the tools shown in the scratchpad. Do not hallucinate.
3. If some steps failed, gracefully work around them using the data that did succeed.
4. Reference prior conversation context where it adds useful continuity.
5. If the question is about an uploaded SQL file and info is provided above, include that analysis.
6. Do NOT include follow-up suggestions here — they will be appended separately.{clarification_context}

### FINAL ANSWER:"""

    try:
        if state.get("stream"):
            def response_generator():
                full_text = ""
                # 1. Yield the main synthesized response as it streams
                for chunk in llm.stream(synthesis_prompt):
                    full_text += chunk
                    yield chunk
                
                # 2. Once streaming is done, generate suggestions based on the full text
                suggestions_block = _generate_suggestions(llm, state["question"], full_text, config)
                if suggestions_block:
                    yield suggestions_block
            
            state["response"] = response_generator()
            return state

        answer = _invoke_with_timeout(llm, synthesis_prompt, timeout_seconds=60)

        # Append contextual next-step suggestions to every non-streamed response
        suggestions_block = _generate_suggestions(llm, state["question"], answer, config)
        state["response"] = answer + suggestions_block

    except concurrent.futures.TimeoutError:
        state["response"] = (
            "The synthesis step timed out. Here is the raw gathered data:\n\n" + scratchpad
        )
    except Exception as e:
        state["response"] = f"Synthesis failed: {str(e)}"

    return state