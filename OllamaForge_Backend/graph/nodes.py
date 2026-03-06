from services.llm_service import LLMService
from services.wikipedia_service import WikipediaService
from services.website_service import WebsiteService
import time
from core.graph_logger import log_node_execution
from core.token_utils import estimate_tokens

def monitored_node(node_name):
    def decorator(func):
        def wrapper(state, config):
            start_time = time.time()

            input_text = state.get("question", "")

            result = func(state, config)

            execution_time = time.time() - start_time

            output_text = result.get("response", "")

            # If output_text is a generator (streaming), we can't estimate tokens easily without consuming it.
            # We skip token estimation for the output in this case to avoid TypeError.
            if hasattr(output_text, '__iter__') and not isinstance(output_text, (str, list, dict, set)):
                token_usage = estimate_tokens(input_text)
                log_output = "<Streamed Response>"
            else:
                token_usage = estimate_tokens(input_text) + estimate_tokens(output_text)
                log_output = output_text

            log_node_execution(
                session_id=config.get("session_id"),
                node_name=node_name,
                input_data=input_text,
                output_data=log_output,
                execution_time=execution_time,
                token_usage=token_usage
            )

            return result
        return wrapper
    return decorator

@monitored_node("direct_chat")
def direct_chat_node(state, config):
    temperature = config.get("temperature", 0.5)
    llm = LLMService(config["model"], temperature=temperature)
    
    system_prompt = state.get("system_prompt", "")
    stream_flag = state.get("stream", False)

    # Prune history context (Max 10 messages) to prevent Ollama overflow crashing
    recent_history = state.get("history", [])[-10:]

    persona_block = (
        f"### PERSONA\nYou must embody the following persona for this entire conversation:\n{system_prompt}\n"
        if system_prompt else ""
    )

    history_lines = ""
    for msg in recent_history:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        history_lines += f"{role_label}: {msg['content']}\n"

    prompt = f"""{persona_block}### CONVERSATION HISTORY
    {history_lines}
    ### CURRENT TASK
    The user has sent a new message. Read the conversation history above for context,
    then respond to the CURRENT message only. Do not repeat previous answers.
    Be concise, accurate, and stay in character if a persona is defined.
    If the question is ambiguous, ask ONE short clarifying question instead of guessing.

    User: {state['question']}
    Assistant:"""

    try:
        if stream_flag:
            state["response"] = llm.stream(prompt)
        else:
            state["response"] = llm.invoke(prompt)
    except Exception as e:
        state["response"] = f"LLM Error: {str(e)}"
        
    return state

@monitored_node("wikipedia")
def wikipedia_node(state, config):
    wiki = WikipediaService()
    llm = LLMService(config["model"])

    # 1. Smart Query Extraction
    # extraction_prompt = f"""
    # You are an expert search term extractor.
    # Extract the 1 to 3 best Wikipedia search queries from the user's question.
    # Output ONLY a comma-separated list of search terms. No explanation or quotes.
    
    # User Question: {state['question']}
    # """
    
    extraction_prompt = f"""### TASK: Wikipedia Search Query Extraction

    You will receive a user question. Your job is to extract exactly 2 to 3 focused
    Wikipedia search terms that will together give the best coverage to answer it.

    ### RULES
    - Return ONLY a comma-separated list. No numbering, no bullets, no explanation.
    - Each term must be a short noun phrase (2-5 words), not a full sentence.
    - Prefer specific terms over generic ones (e.g. "Apollo 11 mission" > "space").
    - If a named entity (person, place, event) is mentioned, always include it as one term.
    - Do NOT repeat the same concept with different wording.
    - If the question is already a single clear topic, return 2 terms: the exact topic
    and one closely related broader concept.

    ### EXAMPLES
    Question: "What caused the 2008 financial crisis?"
    Output: 2008 financial crisis, subprime mortgage crisis, Lehman Brothers bankruptcy

    Question: "Who invented the telephone?"
    Output: Alexander Graham Bell, invention of the telephone

    ### USER QUESTION
    {state['question']}

    ### OUTPUT (comma-separated terms only):"""

    extracted_str = llm.invoke(extraction_prompt).strip()
    queries = [q.strip() for q in extracted_str.split(',') if q.strip()]
    if not queries:
        queries = [state['question']]
        
    # 2. Multi-Step Execution & Aggregation
    all_context = []
    sources = set()
    
    for q in queries:
        docs = wiki.fetch(q)
        for d in docs:
            all_context.append(f"Title: {d['title']}\nContent: {d['content']}")
            if d['source'] != "No URL":
                sources.add(d['source'])
                
    # 3. Graceful Error Handling & Final Prompt
    if not all_context:
        state["response"] = "I couldn't find information on Wikipedia regarding that."
        return state
        
    context_str = "\n\n---\n\n".join(all_context)
    
    # prompt = f"""
    # Use this aggregated Wikipedia content to answer the user's question:

    # {context_str}

    # User Question: {state['question']}
    
    # Instructions:
    # Answer clearly using ONLY the provided facts. 
    # At the very end of your answer, append a 'Sources:' section listing the following exact URLs:
    # {', '.join(sources)}
    # """
    sources_list = "\n".join([f"- {s}" for s in sources]) if sources else "- No sources available"

    answer_prompt = f"""### TASK: Answer from Wikipedia Context

    You are a factual research assistant. Using ONLY the Wikipedia content provided below,
    answer the user's question as accurately and completely as possible.

    ### STRICT RULES
    1. Use ONLY facts from the provided context. Do not add outside knowledge.
    2. If the context partially answers the question, state what IS known and clearly flag
    what is NOT covered: "Note: The provided sources do not mention [X]."
    3. If the context is entirely irrelevant, reply: "The retrieved Wikipedia content does
    not contain enough information to answer this question."
    4. Keep your answer focused. Avoid repeating the same fact in different words.
    5. Use plain prose. Use bullet points only for lists of 3 or more distinct items.

    ### WIKIPEDIA CONTEXT
    {context_str}

    ### USER QUESTION
    {state['question']}

    ### YOUR ANSWER
    [Write your answer here]

    ### SOURCES
    {sources_list}"""

    if state.get("stream"):
        state["response"] = llm.stream(answer_prompt)
    else:
        state["response"] = llm.invoke(answer_prompt)
    return state

@monitored_node("rag")
def rag_node(state, config):
    rag_service = config["rag"]
    llm = LLMService(config["model"])

    context = rag_service.retrieve(state["question"])

    # prompt = f"""
    # Answer using this context:

    # {context}

    # Question:
    # {state['question']}
    # """

    rag_prompt = f"""### TASK: Document Question Answering (RAG)

    You are a precise document analyst. The context below consists of passages retrieved
    from a user's uploaded document. Answer the user's question using ONLY these passages.

    ### RETRIEVED DOCUMENT PASSAGES
    {context}

    ### USER QUESTION
    {state['question']}

    ### INSTRUCTIONS
    1. Base your answer strictly on the passages above. Do not use outside knowledge.
    2. If the answer is directly stated in the text, quote the relevant phrase briefly,
    then explain it in plain language.
    3. If the answer requires combining information from multiple passages, synthesize
    them into a single coherent response.
    4. If the passages do not contain enough information to answer the question, say:
    "The uploaded document does not appear to contain information about [topic].
        You may want to upload a more relevant document or rephrase your question."
    5. Keep your response clear and appropriately concise for the complexity of the question.

    ### ANSWER:"""

    if state.get("stream"):
        state["response"] = llm.stream(rag_prompt)
    else:
        state["response"] = llm.invoke(rag_prompt)
    return state

# def database_node(state, config):

import re

def extract_sql(query_text: str) -> str:
    # Extract SQL from ```sql block
    match = re.search(r"```sql(.*?)```", query_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: extract first SELECT statement
    match = re.search(r"(SELECT .*?;)", query_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return query_text.strip()

@monitored_node("website")
def website_node(state, config):
    urls = state.get("urls") or state.get("url")
    llm = LLMService(config["model"])
    rag_service = config.get("rag")

    if not urls:
        state["response"] = "Please provide a valid website URL or list of URLs to scrape."
        return state

    web_service = WebsiteService()
    result = web_service.fetch(urls, rag_service)

    # 1. Smart Fallback Branch
    if result["type"] == "error":
        import logging
        logging.warning(f"Website Scraping Failed. Pivoting to Wikipedia Fallback. Error: {result['content']}")
        wiki = WikipediaService()
        wiki_docs = wiki.fetch(state["question"])
        if not wiki_docs:
            state["response"] = f"Failed to scrape website, and Wikipedia had no relevant information. Original Error: {result['content']}"
            return state
            
        wiki_context = "\n\n".join([f"Title: {d['title']}\nContent: {d['content']}" for d in wiki_docs])
        sources = set([d['source'] for d in wiki_docs if d['source'] != "No URL"])
        # prompt = f"""
        # [FALLBACK MODE] The requested website(s) blocked extraction. Therefore, answer using this Wikipedia content instead:
        # {wiki_context}
        # ---
        # Question: {state['question']}
        # Answer clearly and cite: {', '.join(sources)}
        # """

        wiki_fallback_prompt = f"""### TASK: Answer from Wikipedia (Website Fallback)

        Note: The originally requested website could not be accessed. The following content
        was retrieved from Wikipedia as an alternative source. Answer accordingly.

        ### WIKIPEDIA CONTENT
        {wiki_context}

        ### USER QUESTION
        {state['question']}

        ### INSTRUCTIONS
        1. Clearly inform the user at the start of your response that the website was
        unavailable and this answer is based on Wikipedia instead.
        2. Answer the question using only the provided Wikipedia content.
        3. End your response with a "Sources:" section listing these URLs:
        {chr(10).join(f'- {s}' for s in sources)}

        ### ANSWER:"""

        if state.get("stream"):
            state["response"] = llm.stream(wiki_fallback_prompt)
        else:
            state["response"] = llm.invoke(wiki_fallback_prompt)
        return state

    # 2. RAG Branch (Massive Documents)
    if result["type"] == "rag" and rag_service:
        context = rag_service.retrieve(state["question"])
        # prompt = f"""
        # Use the following retrieved website chunks to answer the user's question:
        # {context}
        # ---
        # Question: {state['question']}
        # Answer clearly and cite information directly from the provided text.
        # """

        rag_web_prompt = f"""### TASK: Answer from Indexed Website Chunks

        You are a web research assistant. The passages below are the most relevant sections
        retrieved from an indexed version of the requested website.

        ### RETRIEVED WEBSITE CHUNKS
        {context}

        ### USER QUESTION
        {state['question']}

        ### INSTRUCTIONS
        1. Synthesize the retrieved chunks to form a complete, accurate answer.
        2. Ignore any chunk that appears to be navigation, ads, or non-informational text.
        3. If multiple chunks provide complementary information, combine them coherently.
        4. Cite specific details (numbers, names, dates) that appear in the chunks.
        5. If the chunks are insufficient, state what is and isn't covered.

        ### ANSWER:"""

        if state.get("stream"):
            state["response"] = llm.stream(rag_web_prompt)
        else:
            state["response"] = llm.invoke(rag_web_prompt)
        return state

    # 3. Standard Text Branch (Small/Medium Documents)
    # prompt = f"""
    # Use the following aggregated website content to answer the user's question:
    # {result['content']}
    # ---
    # Question: {state['question']}
    # Answer clearly and cite information directly from the provided text.
    # """

    standard_prompt = f"""### TASK: Answer from Website Content

    You are a web research assistant. The content below was scraped from the requested
    website(s). Use it to answer the user's question.

    ### WEBSITE CONTENT
    {result['content']}

    ### USER QUESTION
    {state['question']}

    ### INSTRUCTIONS
    1. Answer using ONLY information present in the website content above.
    2. Ignore boilerplate text (nav menus, cookie notices, footer text, ads).
    Focus on the main article or informational content.
    3. Be specific: if the site mentions numbers, dates, or names relevant to the
    question, include them.
    4. If the site content is irrelevant to the question, clearly state:
    "The scraped content from this website does not address your question."
    5. Do not fabricate URLs or statistics not present in the content.

    ### ANSWER:"""

    if state.get("stream"):
        state["response"] = llm.stream(standard_prompt)
    else:
        state["response"] = llm.invoke(standard_prompt)
    return state

@monitored_node("database")
def database_node(state, config):
    db_service = config["db"]
    llm = LLMService(config["model"])
    
    # 1. Fetch schema and dialect
    schema_info = db_service.get_schema()
    dialect = db_service.get_dialect()

    # 2. Step 1: Generate SQL from Natural Language
    # sql_gen_prompt = f"""
    # You are an expert SQL Data Analyst specializing in {dialect} database.
    # Your task is to convert the user's natural language question into a high-quality, efficient {dialect} SQL query.

    # Database Schema:
    # {schema_info}

    # User Question: {state['question']}

    # Instructions:
    # - Use ONLY {dialect} compatible syntax.
    # - If the user asks to 'summarize' or 'overview' and you query 'sqlite_master', remember that the column name for tables is 'name' (NOT 'TABLE_NAME').
    # - For summaries, NEVER use 'SELECT *' inside a sub-select or string concatenation (e.g., 'SELECT ... || (SELECT * FROM ...)'). SQLite only allows sub-selects that return a SINGLE column and a SINGLE row in such contexts.
    # - Instead of complex concatenations, write separate queries or use simple 'SELECT count(*) FROM table' to get metadata.
    # - If the user asks for a summary, aim for a query that lists table names and their approximate sizes if possible, but keep it simple enough to be valid SQL.
    # - Do NOT include any explanations or conversation in your response.
    # - Return ONLY the SQL query.
    # """

    # Build dialect-specific guardrails dynamically
    dialect_rules = {
        "sqlite": """
    - Use only SQLite-compatible syntax.
    - For schema introspection, use: SELECT name FROM sqlite_master WHERE type='table';
    - Do NOT use sub-selects that return multiple columns or rows inside string contexts.
    - For row counts, use: SELECT COUNT(*) FROM table_name;
    - Do NOT use window functions unless the SQLite version is known to support them.""",
        "mysql": """
    - Use only MySQL-compatible syntax.
    - For schema introspection, use: SHOW TABLES; or SELECT TABLE_NAME FROM information_schema.TABLES;
    - Use backticks for identifiers, not double quotes.""",
        "postgresql": """
    - Use only PostgreSQL-compatible syntax.
    - For schema introspection, use: SELECT tablename FROM pg_tables WHERE schemaname='public';
    - Use double quotes for identifiers with special characters.""",
    }
    dialect_specific = dialect_rules.get(dialect.lower(), f"- Use only {dialect}-compatible syntax.")

    sql_gen_prompt = f"""### TASK: Natural Language to SQL

    You are a senior {dialect} database engineer. Convert the user's question into a
    single, executable {dialect} SQL query using the schema provided.

    ### DATABASE SCHEMA
    {schema_info}

    ### DIALECT-SPECIFIC RULES
    {dialect_specific}

    ### UNIVERSAL RULES
    1. Output ONLY the raw SQL query. No markdown, no backticks, no explanation,
    no preamble, no trailing text.
    2. Always add LIMIT 100 to any SELECT query that could return many rows,
    unless the user explicitly asks for all records.
    3. Use only table and column names that exist in the schema above. Never invent names.
    4. If a JOIN is required, use explicit JOIN ... ON syntax, not implicit comma joins.
    5. If the question is unanswerable with the given schema, output exactly:
    -- UNANSWERABLE: [one-sentence reason]
    6. Prefer readability: use table aliases and newlines for complex queries.

    ### USER QUESTION
    {state['question']}

    ### SQL QUERY:"""

    try:
        raw_response = llm.invoke(sql_gen_prompt)
    except Exception as e:
        state["response"] = f"LLM Generation Error: {str(e)}"
        return state

    # 3. Step 2: Strict SQL Parsing & Refinement
    # This ensures no natural language 'noise' remains in the final query.
    # refine_prompt = f"""
    # You are a strict SQL extractor. 
    # From the following text, extract ONLY the executable {dialect} SQL query.
    # Remove any markdown formatting (like ```sql), conversational text, or explanations.
    # If multiple queries are present, return only the most relevant one.
    
    # Raw Text:
    # {raw_response}
    
    # Executable SQL:
    # """

    refine_prompt = f"""### TASK: SQL Extraction and Validation

    From the raw text below, extract the single executable {dialect} SQL query.

    ### RAW TEXT
    {raw_response}

    ### EXTRACTION RULES
    1. Remove ALL markdown formatting: backticks, ```sql blocks, language tags.
    2. Remove all natural language text, comments, and explanations.
    3. If multiple SQL statements are present, return only the LAST one
    (it is typically the most refined version).
    4. If the raw text contains "-- UNANSWERABLE:", return that line exactly as-is.
    5. If no valid SQL can be extracted, return exactly: SELECT 'extraction_failed' AS error;
    6. Do NOT modify the SQL logic — only clean up formatting.
    7. Output ONLY the final SQL. No labels, no explanation, no punctuation after the query.

    ### EXTRACTED SQL:"""

    try:
        clean_sql = llm.invoke(refine_prompt).strip()
        # Edge case: sometimes it still adds markdown
        if "```" in clean_sql:
            import re
            match = re.search(r"```sql(.*?)```", clean_sql, re.DOTALL | re.IGNORECASE)
            if match:
                clean_sql = match.group(1).strip()
            else:
                clean_sql = clean_sql.replace("```sql", "").replace("```", "").strip()
    except Exception as e:
        state["response"] = f"SQL Parsing Error: {str(e)}"
        return state

    # 4. Execute the refined SQL
    try:
        sql_result = db_service.execute(clean_sql)
    except Exception as e:
        state["response"] = f"SQL Execution Error: {str(e)}\nExecuted SQL: {clean_sql}"
        return state

    # 5. Step 3: Synthesis (Natural Language Interpretation)
    synthesis_prompt = f"""### TASK: SQL Result Interpretation
    
    You are a data analyst. Based on the user's question and the raw data retrieved
    from the database, provide a clear, helpful, and natural language response.

    ### USER QUESTION
    {state['question']}

    ### EXECUTED SQL
    {clean_sql}

    ### RAW SQL DATA
    {sql_result}

    ### INSTRUCTIONS
    1. Summarize the data in a way that directly answers the user's question.
    2. If the data is a table, describe the key findings or trends.
    3. Use a professional yet conversational tone.
    4. If the data is empty, explain that no matching records were found.
    5. Do not mention technical details like SQL syntax or table names unless necessary.
    6. If the data contains specific numbers or units, include them accurately.

    ### FINAL ANSWER:"""

    try:
        if state.get("stream"):
            state["response"] = llm.stream(synthesis_prompt)
        else:
            state["response"] = llm.invoke(synthesis_prompt)
    except Exception as e:
        state["response"] = f"Synthesis Error: {str(e)}\nRaw Data: {sql_result}"

    return state