# workflow/state.py
from typing import TypedDict, List, Dict, Any, Annotated
import operator


class ResearchState(TypedDict, total=False):
    """
    Define the global state for LangGraph workflow orchestration.
    This acts as the shared 'task whiteboard' for the multi-agent team.
    """
    # 1. Initial Inputs
    research_topic: str
    min_papers: int  # Minimum number of papers to retrieve

    # 2. Planner Outputs
    sub_questions: List[str]
    concept_map: str  # [Phase 4] Mermaid conceptual topology map

    # 3. Screener Outputs
    candidate_papers: List[Dict[str, Any]]  # Metadata for all initially retrieved papers
    selected_papers: List[Dict[str, Any]]  # Papers filtered for downloading and deep reading

    # 4. Reader Outputs (Core Highlight: uses operator.add to support concurrent content appending)
    extracted_insights: Annotated[List[str], operator.add]

    # 5. DataMiner Outputs: Structured quantitative metrics
    quantitative_data: List[Dict[str, str]]

    # 6. Writer & Reviewer Outputs
    draft: str
    review_comments: str

    # 🔴 Day 22: Multi-turn interaction and revisions
    user_feedback: str  # Latest instruction input from the user chat box
    chat_history: List[Dict]  # Historical conversation context [{"role": "user"/"assistant", "content": "..."}]
    
    # 🔴 Phase 4: Domain terminology dictionary
    jargon_dictionary: List[Dict[str, str]]
    
    # 🔴 Phase 6: Critical review checklist (Red Team Analysis)
    critical_checklist: List[Dict[str, str]]
    
    # 🔴 Phase 8: Agent thought-stream logs
    logs: Annotated[List[str], operator.add]

    # 6. Safety Guard: Track revision count to prevent infinite rewrite loops
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
