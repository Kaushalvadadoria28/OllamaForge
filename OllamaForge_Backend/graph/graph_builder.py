from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from graph.nodes import (
    supervisor_router_node,
    rag_node,
    database_node,
    wikipedia_node,
    website_node,
    final_synthesis_node,
)
from graph.context_discovery import discover_workspace_context, handle_ambiguous_query


# ═══════════════════════════════════════════════════════════════════
# AGENT STATE SCHEMA
# ═══════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    question:        str
    response:        str
    history:         List[Dict[str, str]]  # Full conversation history for context continuity
    urls:            Any                   # Optional URL(s) for website node
    system_prompt:   str
    stream:          bool
    temperature:     float
    # ── Agentic tracking fields ──────────────────────────────────────
    next_action:     str   # Which tool to invoke next ('rag','db','wiki','web','complete')
    tool_output:     str   # Raw result or error from the last tool execution
    agent_scratchpad: str  # Running log of [Thought] + [Observation] steps
    # ── Context discovery fields ────────────────────────────────────
    _context_clues:  Dict[str, Any]  # Metadata about workspace and intent
    _workspace_context: str  # Human-readable workspace context block
    _clarification_needed: bool  # Flag: does user need to answer clarifying questions?
    _clarification_questions: List[Dict[str, Any]]  # Structured questions to ask user


# ═══════════════════════════════════════════════════════════════════
# ROUTING FUNCTION
# ═══════════════════════════════════════════════════════════════════

def choice_router(state: AgentState) -> str:
    """
    Reads next_action from state and returns the name of the graph node
    to route to. Any unknown or missing value safely falls through to
    'synthesize' instead of raising a KeyError (FIX #10).
    """
    next_step = state.get("next_action", "complete")
    valid_tool_routes = {"rag", "db", "wiki", "web"}

    if next_step in valid_tool_routes:
        return next_step

    # 'complete' or any unexpected value → go to final synthesis
    return "synthesize"


# ═══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════

def build_graph(source: Optional[str], config: dict):
    """
    Builds and compiles the full LangGraph agentic workflow.

    The `source` parameter (FIX #3) is used to:
      1. Pre-seed `_source_hint` in config so nodes know the caller's intent.
      2. The initial state factory (create_initial_state) uses it to pre-seed
         `next_action`, giving the supervisor a directional nudge on its very
         first routing decision without bypassing agentic flexibility.

    Args:
        source:  Caller hint for the primary data source. One of:
                 'RAG' | 'Database' | 'Wikipedia' | 'Website' | None
        config:  Runtime config dict passed through to every node.
    """
    SOURCE_ACTION_MAP = {
        "RAG":       "rag",
        "Database":  "db",
        "Wikipedia": "wiki",
        "Website":   "web",
    }

    initial_action_hint = SOURCE_ACTION_MAP.get(source, "") if source else ""
    config["_source_hint"] = initial_action_hint  # Available to nodes if needed

    # ── Build the state graph ────────────────────────────────────────
    builder = StateGraph(AgentState)

    # ── NEW: Context discovery runs first to enrich state ──
    builder.add_node("discover_context", lambda s: discover_workspace_context(s, config))
    builder.add_node("check_ambiguity", lambda s: handle_ambiguous_query(s, config))

    # Register all tool nodes
    builder.add_node("supervisor", lambda s: supervisor_router_node(s, config))
    builder.add_node("rag",        lambda s: rag_node(s, config))
    builder.add_node("db",         lambda s: database_node(s, config))
    builder.add_node("wiki",       lambda s: wikipedia_node(s, config))
    builder.add_node("web",        lambda s: website_node(s, config))
    builder.add_node("synthesize", lambda s: final_synthesis_node(s, config))

    # Entry point: Start with context discovery for every graph run
    builder.set_entry_point("discover_context")

    # Context discovery → Ambiguity check
    builder.add_edge("discover_context", "check_ambiguity")
    
    # Ambiguity check → Supervisor (with enriched context)
    builder.add_edge("check_ambiguity", "supervisor")

    # Conditional branching: supervisor → tool node OR synthesize
    builder.add_conditional_edges(
        "supervisor",
        choice_router,
        {
            "rag":       "rag",
            "db":        "db",
            "wiki":      "wiki",
            "web":       "web",
            "synthesize": "synthesize",
        },
    )

    # After each tool, cycle back to supervisor for re-evaluation
    builder.add_edge("rag",  "supervisor")
    builder.add_edge("db",   "supervisor")
    builder.add_edge("wiki", "supervisor")
    builder.add_edge("web",  "supervisor")

    # Terminal: synthesize → END
    builder.add_edge("synthesize", END)

    return builder.compile()


# ═══════════════════════════════════════════════════════════════════
# INITIAL STATE FACTORY
# ═══════════════════════════════════════════════════════════════════

def create_initial_state(
    question:      str,
    history:       Optional[List[Dict[str, str]]] = None,
    urls:          Any = None,
    system_prompt: str = "",
    stream:        bool = False,
    temperature:   float = 0.5,
    source:        Optional[str] = None,
) -> AgentState:
    """
    Constructs a clean AgentState for a fresh graph invocation.

    IMPORTANT (FIX #2): Always use this factory at your chat endpoint
    instead of passing a raw dict, to ensure `next_action` is correctly
    pre-seeded from `source` before the supervisor's first call.

    Usage in your chat endpoint:
        from graph.graph_builder import create_initial_state, build_graph

        state  = create_initial_state(
            question=user_question,
            history=session_history,
            source=session_source,   # e.g. "RAG" loaded from your session DB
            stream=True,
        )
        result = graph.invoke(state)

    Args:
        question:      The user's query string.
        history:       Prior conversation turns [{"role": "user"|"assistant", "content": "..."}].
        urls:          URL string or list for the web scraping node.
        system_prompt: Custom system-level instructions.
        stream:        True to stream the final synthesis response.
        temperature:   LLM creativity for final synthesis (0.0 – 1.0).
        source:        Caller hint: 'RAG' | 'Database' | 'Wikipedia' | 'Website' | None.
    """
    SOURCE_ACTION_MAP = {
        "RAG":       "rag",
        "Database":  "db",
        "Wikipedia": "wiki",
        "Website":   "web",
    }
    initial_action = SOURCE_ACTION_MAP.get(source, "") if source else ""

    return AgentState(
        question        = question,
        response        = "",
        history         = history or [],
        urls            = urls,
        system_prompt   = system_prompt,
        stream          = stream,
        temperature     = temperature,
        next_action     = initial_action,  # Pre-seeded from source (FIX #2 + #3)
        tool_output     = "",
        agent_scratchpad = "",
        # ── Context discovery fields (initialized empty) ──
        _context_clues  = {},
        _workspace_context = "",
        _clarification_needed = False,
        _clarification_questions = [],
    )





# # from langgraph.graph import StateGraph, END
# # from graph.nodes import (
# #     direct_chat_node,
# #     rag_node,
# #     database_node,
# #     wikipedia_node,
# #     website_node
# # )

# # from typing import TypedDict, List, Dict, Any

# # class AgentState(TypedDict):
# #     question: str
# #     response: str
# #     history: List[Dict[str, str]]
# #     urls: Any
# #     system_prompt: str
# #     stream: bool
# #     # --- Agentic Tracking State Fields ---
# #     next_action: str          # Tracks which tool node to route to next
# #     tool_output: str          # Stores the raw result or errors from the last executed tool
# #     agent_scratchpad: str     # Keeps a running log of the LLM's multi-step thoughts

# # def build_graph(source, config):

# #     builder = StateGraph(dict)

# #     if source == "RAG":
# #         builder.add_node("rag", lambda s: rag_node(s, config))
# #         builder.set_entry_point("rag")
# #         builder.add_edge("rag", END)

# #     elif source == "Database":
# #         builder.add_node("db", lambda s: database_node(s, config))
# #         builder.set_entry_point("db")
# #         builder.add_edge("db", END)

# #     elif source == "Wikipedia":
# #         builder.add_node("wiki", lambda s: wikipedia_node(s, config))
# #         builder.set_entry_point("wiki")
# #         builder.add_edge("wiki", END)

# #     elif source == "Website":
# #         builder.add_node("web", lambda s: website_node(s, config))
# #         builder.set_entry_point("web")
# #         builder.add_edge("web", END)

# #     else:
# #         builder.add_node("chat", lambda s: direct_chat_node(s, config))
# #         builder.set_entry_point("chat")
# #         builder.add_edge("chat", END)

# #     return builder.compile()
# from typing import TypedDict, List, Dict, Any
# from langgraph.graph import StateGraph, END
# from graph.nodes import (
#     supervisor_router_node,
#     rag_node,
#     database_node,
#     wikipedia_node,
#     website_node,
#     final_synthesis_node
# )

# # 1. Define explicit Agent State Schema
# class AgentState(TypedDict):
#     question: str
#     response: str
#     history: List[Dict[str, str]]
#     urls: Any
#     system_prompt: str
#     stream: bool
#     next_action: str          # Tracks which tool node to route to next
#     tool_output: str          # Stores the raw result or errors from the last executed tool
#     agent_scratchpad: str     # Keeps a running log of the LLM's multi-step thoughts

# def choice_router(state: AgentState):
#     """
#     Evaluates the supervisor's decision state string and routes control flow.
#     """
#     next_step = state.get("next_action")
#     if next_step == "complete" or not next_step:
#         return "synthesize"
#     return next_step  # Dynamic routing to 'rag', 'db', 'wiki', or 'web'

# def build_graph(source, config):
#     # Using explicit AgentState ensures reliable properties mutation updates
#     builder = StateGraph(AgentState)

#     # Define processing node blocks
#     builder.add_node("supervisor", lambda s: supervisor_router_node(s, config))
#     builder.add_node("rag", lambda s: rag_node(s, config))
#     builder.add_node("db", lambda s: database_node(s, config))
#     builder.add_node("wiki", lambda s: wikipedia_node(s, config))
#     builder.add_node("web", lambda s: website_node(s, config))
#     builder.add_node("synthesize", lambda s: final_synthesis_node(s, config))

#     # Establish entry gate hook
#     builder.set_entry_point("supervisor")

#     # Wire conditional branching logic map
#     builder.add_conditional_edges(
#         "supervisor",
#         choice_router,
#         {
#             "rag": "rag",
#             "db": "db",
#             "wiki": "wiki",
#             "web": "web",
#             "synthesize": "synthesize"
#         }
#     )

#     # Direct cycling outputs back up into supervisor evaluation clearinghouse
#     builder.add_edge("rag", "supervisor")
#     builder.add_edge("db", "supervisor")
#     builder.add_edge("wiki", "supervisor")
#     builder.add_edge("web", "supervisor")
    
#     # Graph processing completion terminal
#     builder.add_edge("synthesize", END)

#     return builder.compile()

# from typing import TypedDict, List, Dict, Any, Optional
# from langgraph.graph import StateGraph, END
# from graph.nodes import (
#     supervisor_router_node,
#     rag_node,
#     database_node,
#     wikipedia_node,
#     website_node,
#     final_synthesis_node,
# )


# # ─────────────────────────────────────────────
# # AGENT STATE SCHEMA
# # ─────────────────────────────────────────────

# class AgentState(TypedDict):
#     question: str
#     response: str
#     history: List[Dict[str, str]]   # FIX #5: history is now explicit in the schema
#     urls: Any
#     system_prompt: str
#     stream: bool
#     temperature: float
#     # --- Agentic Tracking State Fields ---
#     next_action: str        # Tracks which tool node to route to next
#     tool_output: str        # Stores the raw result or errors from the last executed tool
#     agent_scratchpad: str   # Keeps a running log of the LLM's multi-step thoughts and observations


# # ─────────────────────────────────────────────
# # ROUTING FUNCTION
# # ─────────────────────────────────────────────

# def choice_router(state: AgentState) -> str:
#     """
#     Evaluates the supervisor's decision and routes to the correct node.

#     FIX #10: Includes an explicit unknown-action guard — any unrecognised
#     value falls through to 'synthesize' instead of raising a KeyError.
#     """
#     next_step = state.get("next_action", "complete")
#     valid_tool_routes = {"rag", "db", "wiki", "web"}

#     if next_step in valid_tool_routes:
#         return next_step

#     # 'complete' or any unexpected/malformed value → synthesize
#     return "synthesize"


# # ─────────────────────────────────────────────
# # GRAPH BUILDER
# # ─────────────────────────────────────────────

# def build_graph(source: Optional[str], config: dict):
#     """
#     Builds and compiles the LangGraph agentic workflow.

#     FIX #3: The `source` parameter is now used to pre-seed `next_action`
#     in the initial state hint, giving the supervisor a directional nudge
#     without bypassing it entirely. This preserves agentic flexibility while
#     honouring the caller's intent.

#     Args:
#         source: Optional hint about the primary data source the caller
#                 expects to be used. One of: 'RAG', 'Database', 'Wikipedia',
#                 'Website', or None for open routing.
#         config:  Runtime config dict passed through to every node.
#     """

#     # Map caller-supplied source labels to internal action strings
#     SOURCE_ACTION_MAP = {
#         "RAG": "rag",
#         "Database": "db",
#         "Wikipedia": "wiki",
#         "Website": "web",
#     }

#     # Pre-seed next_action from source hint so the supervisor's first
#     # decision is already informed. The supervisor can still override
#     # this on subsequent cycles based on what it observes.
#     initial_action_hint = SOURCE_ACTION_MAP.get(source, "") if source else ""

#     # Store the hint in config so nodes can access it if needed.
#     # The supervisor will read next_action from state on first call.
#     config["_source_hint"] = initial_action_hint

#     # ── Build the state graph ────────────────────────────────────────
#     builder = StateGraph(AgentState)

#     # Define all processing node blocks
#     builder.add_node("supervisor", lambda s: supervisor_router_node(s, config))
#     builder.add_node("rag",        lambda s: rag_node(s, config))
#     builder.add_node("db",         lambda s: database_node(s, config))
#     builder.add_node("wiki",       lambda s: wikipedia_node(s, config))
#     builder.add_node("web",        lambda s: website_node(s, config))
#     builder.add_node("synthesize", lambda s: final_synthesis_node(s, config))

#     # Entry gate: every execution starts at the supervisor
#     builder.set_entry_point("supervisor")

#     # Conditional branching from supervisor → tool or synthesize
#     builder.add_conditional_edges(
#         "supervisor",
#         choice_router,
#         {
#             "rag":       "rag",
#             "db":        "db",
#             "wiki":      "wiki",
#             "web":       "web",
#             "synthesize": "synthesize",
#         },
#     )

#     # After each tool node completes, cycle back to supervisor for re-evaluation
#     builder.add_edge("rag",  "supervisor")
#     builder.add_edge("db",   "supervisor")
#     builder.add_edge("wiki", "supervisor")
#     builder.add_edge("web",  "supervisor")

#     # Terminal edge: synthesize → END
#     builder.add_edge("synthesize", END)

#     return builder.compile()


# # ─────────────────────────────────────────────
# # INITIAL STATE FACTORY
# # ─────────────────────────────────────────────

# def create_initial_state(
#     question: str,
#     history: Optional[List[Dict[str, str]]] = None,
#     urls: Any = None,
#     system_prompt: str = "",
#     stream: bool = False,
#     temperature: float = 0.5,
#     source: Optional[str] = None,
# ) -> AgentState:
#     """
#     Factory function that constructs a clean AgentState for a new invocation.

#     FIX #3: Applies the source hint directly to `next_action` so the
#     supervisor's very first routing decision is pre-informed.

#     Args:
#         question:      The user's query.
#         history:       Prior conversation turns for continuity.
#         urls:          Optional URL(s) for the web node.
#         system_prompt: Custom system-level instructions.
#         stream:        Whether to stream the final response.
#         temperature:   Synthesis creativity level (0.0 – 1.0).
#         source:        Caller hint for primary data source.
#     """
#     SOURCE_ACTION_MAP = {
#         "RAG": "rag",
#         "Database": "db",
#         "Wikipedia": "wiki",
#         "Website": "web",
#     }
#     initial_action = SOURCE_ACTION_MAP.get(source, "") if source else ""

#     return AgentState(
#         question=question,
#         response="",
#         history=history or [],
#         urls=urls,
#         system_prompt=system_prompt,
#         stream=stream,
#         temperature=temperature,
#         next_action=initial_action,   # Pre-seeded from source hint
#         tool_output="",
#         agent_scratchpad="",
#     )