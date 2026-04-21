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
    条件路由函数：决定 Reviewer 审核后的下一步走向。
    """
    if "PASS" in state.get("review_comments", ""):
        return "end"  # 审核通过，走向终点
    else:
        return "rewrite"  # 审核失败，打回重写


def build_research_graph():
    print("⚙️ 正在组装 LangGraph 工作流引擎...")
    workflow = StateGraph(ResearchState)

    # ==========================================
    # 1. 注册所有节点
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
    # 2. 定义魔法路由：入口分发器
    # ==========================================
    def route_start(state: ResearchState):
        """如果状态里有 user_feedback，说明是多轮对话，直奔 Editor；否则走常规 Planner"""
        if state.get("user_feedback"):
            return "Editor"
        return "Planner"

    # 🔴 设定条件入口 (注意：有了这个，绝对不能再写 set_entry_point 了)
    workflow.set_conditional_entry_point(
        route_start,
        {"Editor": "Editor", "Planner": "Planner"}
    )

    # ==========================================
    # 3. 定义常规边 (流水线顺序)
    # ==========================================
    workflow.add_edge("Planner", "Screener")
    workflow.add_edge("Screener", "Reader")

    # 🔴 修复分支冲突：Reader -> DataMiner -> Writer 必须是单行道
    workflow.add_edge("Reader", "DataMiner")
    workflow.add_edge("DataMiner", "Writer")

    workflow.add_edge("Writer", "Reviewer")

    # 🔴 补全节点缺失：Editor 完工后，直接走向图的终点
    workflow.add_edge("Editor", END)

    # ==========================================
    # 4. 定义条件边 (防幻觉循环)
    # ==========================================
    workflow.add_conditional_edges(
        "Reviewer",
        route_review,
        {
            "rewrite": "Writer",  # 如果路由返回 rewrite，打回给 Writer
            "end": "Critic"  # 如果路由返回 end，过渡到批判水晏分析器
        }
    )
    workflow.add_edge("Critic", END)  # Critic 完成后看图流程结束

    # ==========================================
    # 5. 编译与状态快照（已升级为 SQLite 持久化）
    # ==========================================
    import sqlite3
    import os
    os.makedirs("./workspace", exist_ok=True)
    
    conn = sqlite3.connect("./workspace/research_mem.db", check_same_thread=False)
    memory = SqliteSaver(conn)
    
    app = workflow.compile(
        checkpointer=memory,
        # 🔴 Phase 8: 增加 Screener 与 Reader 的二次干预断点
        interrupt_before=["Screener", "Reader"]
    )
    print("✅ 图组装完毕！已启用 SQLite 持久化、双重 HITL 断点以及思维流机制。")
    return app