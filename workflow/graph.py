from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, END, START
from workflow.state import ResearchState
from workflow.nodes import (
    planner_node,
    screener_node,
    reader_node,
    writer_node,
    reviewer_node,
    data_miner_node,
    editor_node,
    critic_node
)


def route_review(state: ResearchState) -> str:
    """
    Conditional routing function: decides the next step after the Reviewer's check.
    """
    if "PASS" in state.get("review_comments", ""):
        return "end"  # Review passed, route to the end
    else:
        return "rewrite"  # Review failed, route back for rewrite


def build_research_graph():
    print("⚙️ 正在组装 LangGraph 工作流引擎...")
    workflow = StateGraph(ResearchState)

    # ==========================================
    # 1. Register all nodes
    # ==========================================
    workflow.add_node("Planner", planner_node)
    workflow.add_node("Screener", screener_node)
    workflow.add_node("Reader", reader_node)
    workflow.add_node("DataMiner", data_miner_node)
    workflow.add_node("Writer", writer_node)
    workflow.add_node("Reviewer", reviewer_node)
    workflow.add_node("Editor", editor_node)
    workflow.add_node("Critic", critic_node)

    # ==========================================
    # 2. Define magic routing: Entry dispatcher
    # ==========================================
    def route_start(state: ResearchState):
        """If there is user_feedback in the state, it's a multi-turn conversation, route to Editor; otherwise, normal Planner."""
        if state.get("user_feedback"):
            return "Editor"
        return "Planner"

    # 🔴 Set conditional entry point (Note: With this, do NOT use set_entry_point)
    workflow.set_conditional_entry_point(
        route_start,
        {"Editor": "Editor", "Planner": "Planner"}
    )

    # ==========================================
    # 3. Define normal edges (Pipeline sequence)
    # ==========================================
    workflow.add_edge("Planner", "Screener")
    workflow.add_edge("Screener", "Reader")

    # 🔴 Fix branch conflict: Reader -> DataMiner -> Writer must be sequential
    workflow.add_edge("Reader", "DataMiner")
    workflow.add_edge("DataMiner", "Writer")

    workflow.add_edge("Writer", "Reviewer")

    # 🔴 Fill missing node logic: After Editor is done, route directly to END
    workflow.add_edge("Editor", END)

    # ==========================================
    # 4. Define conditional edges (Anti-hallucination loop)
    # ==========================================
    workflow.add_conditional_edges(
        "Reviewer",
        route_review,
        {
            "rewrite": "Writer",  # If routing returns rewrite, push back to Writer
            "end": "Critic"  # If routing returns end, transition to Critic
        }
    )
    workflow.add_edge("Critic", END)  # Process ends after Critic completion

    # ==========================================
    # 5. Compile and state snapshot (upgraded to SQLite persistence)
    # ==========================================
    import sqlite3
    import os
    os.makedirs("./workspace", exist_ok=True)
    
    conn = sqlite3.connect("./workspace/research_mem.db", check_same_thread=False)
    memory = SqliteSaver(conn)
    
    app = workflow.compile(
        checkpointer=memory,
        # 🔴 Phase 8: Add double HITL breakpoints for Screener and Reader
        interrupt_before=["Screener", "Reader"]
    )
    print("✅ 图组装完毕！已启用 SQLite 持久化、双重 HITL 断点以及思维流机制。")
    return app