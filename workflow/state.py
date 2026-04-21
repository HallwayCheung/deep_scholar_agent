# workflow/state.py
from typing import TypedDict, List, Dict, Any, Annotated
import operator


class ResearchState(TypedDict, total=False):
    """
    定义 LangGraph 图流转的全局状态（State）。
    这也是整个多智能体团队共享的“任务白板”。
    """
    # 1. 初始输入
    research_topic: str
    min_papers: int  # 最小获取文献数

    # 2. Planner 产出
    sub_questions: List[str]
    concept_map: str  # [Phase4] Mermaid 概念拓扑图

    # 3. Screener 产出
    candidate_papers: List[Dict[str, Any]]  # 初搜回来的所有论文元数据
    selected_papers: List[Dict[str, Any]]  # 打分过滤后，真正需要下载精读的论文

    # 4. Reader 产出 (核心亮点：使用 operator.add 支持并发追加内容)
    extracted_insights: Annotated[List[str], operator.add]

    # 5. 新增：用于存储 DataMiner 提取的结构化数据
    quantitative_data: List[Dict[str, str]]

    # 6. Writer & Reviewer 产出
    draft: str
    review_comments: str

    # 🔴 Day 22 新增：用于多轮对话与修改
    user_feedback: str  # 用户在聊天框输入的最新指令
    chat_history: List[Dict]  # 记录历史对话上下文 [{"role": "user"/"assistant", "content": "..."}]
    
    # 🔴 Phase 4 新增：术语字典
    jargon_dictionary: List[Dict[str, str]]
    
    # 🔴 Phase 6 新增：批判性审视清单（红队分析）
    critical_checklist: List[Dict[str, str]]
    
    # 🔴 Phase 8 新增：Agent 思维流日志
    logs: Annotated[List[str], operator.add]

    # 6. 工程兜底：记录修改次数，防止无限重写
    revision_count: int


def create_initial_state(research_topic: str = "", user_feedback: str = "", min_papers: int = 5) -> ResearchState:
    return {
        "research_topic": research_topic,
        "min_papers": min_papers,
        "sub_questions": [],
        "candidate_papers": [],
        "selected_papers": [],
        "extracted_insights": [],
        "quantitative_data": [],
        "draft": "",
        "review_comments": "",
        "user_feedback": user_feedback,
        "chat_history": [],
        "concept_map": "",
        "jargon_dictionary": [],
        "critical_checklist": [],
        "local_documents": [],
        "logs": [],
        "revision_count": 0,
    }
