from langgraph.graph import StateGraph, END
from graph.nodes import (
    direct_chat_node,
    rag_node,
    database_node,
    wikipedia_node,
    website_node
)

def build_graph(source, config):

    builder = StateGraph(dict)

    if source == "RAG":
        builder.add_node("rag", lambda s: rag_node(s, config))
        builder.set_entry_point("rag")
        builder.add_edge("rag", END)

    elif source == "Database":
        builder.add_node("db", lambda s: database_node(s, config))
        builder.set_entry_point("db")
        builder.add_edge("db", END)

    elif source == "Wikipedia":
        builder.add_node("wiki", lambda s: wikipedia_node(s, config))
        builder.set_entry_point("wiki")
        builder.add_edge("wiki", END)

    elif source == "Website":
        builder.add_node("web", lambda s: website_node(s, config))
        builder.set_entry_point("web")
        builder.add_edge("web", END)

    else:
        builder.add_node("chat", lambda s: direct_chat_node(s, config))
        builder.set_entry_point("chat")
        builder.add_edge("chat", END)

    return builder.compile()