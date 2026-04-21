# app.py
import re
import time
import uuid
from html import escape

import streamlit as st
from dotenv import load_dotenv

from workflow.graph import build_research_graph
from workflow.state import create_initial_state

load_dotenv()

st.set_page_config(page_title="DeepScholar | Academic AI", page_icon="🏛️", layout="wide")

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --bg-grad: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        --panel: rgba(255, 255, 255, 0.03);
        --panel-border: rgba(255, 255, 255, 0.1);
        --panel-strong: rgba(15, 23, 42, 0.8);
        --line: rgba(255, 255, 255, 0.08);
        --text: #f8fafc;
        --muted: #94a3b8;
        --accent: #3b82f6; /* Premium Blue */
        --accent-glow: rgba(59, 130, 246, 0.5);
        --accent-deep: #2563eb;
        --shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        --shadow-glow: 0 0 20px var(--accent-glow);
    }

    .stApp {
        background: var(--bg-grad) !important;
        background-image: 
            radial-gradient(at 0% 0%, hsla(253,16%,7%,1) 0, transparent 50%), 
            radial-gradient(at 50% 0%, hsla(225,39%,30%,0.2) 0, transparent 50%), 
            radial-gradient(at 100% 0%, hsla(339,49%,30%,0.1) 0, transparent 50%) !important;
        background-attachment: fixed !important;
        color: var(--text);
        font-family: 'Inter', sans-serif;
    }
    
    header { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* Global Glass Panel */
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.6) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid var(--panel-border) !important;
        padding-top: 10px;
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0 !important;
        font-weight: 800;
        letter-spacing: 1px;
        font-size: 16px;
        text-transform: uppercase;
    }

    /* Inputs */
    .stTextArea textarea {
        background-color: rgba(0,0,0,0.2) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid var(--panel-border) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        color: var(--text) !important;
        font-size: 14px !important;
        transition: all 0.3s ease !important;
    }
    .stTextArea textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: var(--shadow-glow) !important;
        outline: none !important;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, var(--accent) 0%, var(--accent-deep) 100%) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 1px !important;
        padding: 12px 0 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4) !important;
        text-transform: uppercase;
    }
    .stButton>button:hover {
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 8px 25px rgba(37, 99, 235, 0.6) !important;
    }

    /* Hero Panel */
    .hero-panel {
        background: var(--panel);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid var(--panel-border);
        border-radius: 24px;
        padding: 30px 40px;
        box-shadow: var(--shadow);
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }
    .hero-panel::before {
        content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
        transform: skewX(-20deg); animation: shine 6s infinite;
    }
    @keyframes shine { 100% { left: 200%; } }

    .hero-kicker {
        color: var(--accent);
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 12px;
        display: inline-block;
        padding: 4px 12px;
        background: rgba(59, 130, 246, 0.1);
        border-radius: 20px;
        border: 1px solid rgba(59, 130, 246, 0.2);
    }
    .hero-title {
        color: #ffffff;
        font-family: 'Crimson Text', serif;
        font-size: 48px;
        line-height: 1.1;
        font-weight: 700;
        margin: 0;
        text-shadow: 0 2px 10px rgba(0,0,0,0.5);
    }
    .hero-subtitle {
        color: var(--muted);
        font-size: 16px;
        line-height: 1.6;
        margin: 16px 0 0 0;
        max-width: 800px;
        font-weight: 300;
    }

    /* Stats Grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 20px;
        margin: 20px 0 24px 0;
    }
    .stat-card {
        background: var(--panel);
        backdrop-filter: blur(16px);
        border: 1px solid var(--panel-border);
        border-radius: 20px;
        padding: 20px;
        box-shadow: var(--shadow);
        transition: transform 0.3s ease;
    }
    .stat-card:hover {
        transform: translateY(-5px);
        border-color: rgba(255,255,255,0.2);
    }
    .stat-label {
        color: var(--muted);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .stat-value {
        color: #ffffff;
        font-size: 32px;
        font-weight: 800;
        margin-top: 10px;
        background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stat-helper {
        color: var(--muted);
        font-size: 12px;
        margin-top: 8px;
        line-height: 1.4;
    }

    /* Status Banner */
    .status-banner {
        border-radius: 16px;
        padding: 16px 20px;
        margin-top: 10px;
        margin-bottom: 24px;
        font-size: 14px;
        font-weight: 500;
        line-height: 1.6;
        border: 1px solid rgba(59, 130, 246, 0.3);
        background: rgba(15, 23, 42, 0.6);
        box-shadow: 0 0 20px rgba(59, 130, 246, 0.1);
        backdrop-filter: blur(10px);
        border-left: 4px solid var(--accent);
    }

    /* Document Container */
    .section-card {
        background: var(--panel);
        border: 1px solid var(--panel-border);
        border-radius: 24px;
        padding: 24px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(20px);
    }

    .academic-draft-container {
        background-color: #f8fafc; /* Keep paper light for readability */
        padding: 60px 70px;
        border-radius: 8px; /* Sharp paper look */
        border: 1px solid #e2e8f0;
        font-family: 'Crimson Text', serif;
        font-size: 19px;
        line-height: 1.9;
        color: #1e293b;
        box-shadow: 0 20px 40px rgba(0,0,0,0.5);
        position: relative;
    }
    .academic-draft-container::before {
        content: ''; position: absolute; top:0; left:0; width:100%; height:100%;
        background: url('https://www.transparenttextures.com/patterns/cream-paper.png');
        opacity: 0.4; pointer-events: none; border-radius: 8px;
    }
    .academic-draft-container h1, .academic-draft-container h2, .academic-draft-container h3 {
        color: #0f172a;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-top: 2em;
        margin-bottom: 1em;
        border-bottom: 2px solid #f1f5f9;
        padding-bottom: 10px;
    }

    /* Tooltips */
    .citation-tooltip {
        color: #2563eb;
        font-weight: 600;
        cursor: help;
        border-bottom: 2px dotted #3b82f6;
        position: relative;
        font-family: 'Inter', sans-serif;
        font-size: 14px;
        padding: 0 4px;
        transition: all 0.2s;
        background: rgba(59, 130, 246, 0.08);
        border-radius: 4px;
    }
    .citation-tooltip:hover { background: rgba(59, 130, 246, 0.15); color: #1e3a8a; }
    .citation-tooltip:hover::after {
        content: attr(data-tooltip);
        position: absolute; bottom: 140%; left: 50%; transform: translateX(-50%);
        background-color: #0f172a; color: #f8fafc;
        padding: 14px 18px; border-radius: 12px;
        font-size: 13px; font-weight: 400; line-height: 1.6;
        width: 340px; white-space: normal; z-index: 9999;
        box-shadow: 0 10px 40px rgba(0,0,0,0.4);
        border: 1px solid rgba(255,255,255,0.1);
        pointer-events: none;
    }

    /* Timeline DAG */
    .timeline-wrapper {
        position: relative; padding-left: 35px; margin-top: 30px; font-family: 'Inter', sans-serif;
    }
    .timeline-wrapper::after {
        content: ''; position: absolute; width: 2px; top: 0; bottom: 0; left: 11px;
        background: linear-gradient(to bottom, var(--accent) 50%, rgba(255,255,255,0.1) 0%);
        background-size: 2px 14px; background-repeat: repeat-y; z-index: 1;
    }
    .node-item {
        position: relative; display: flex; align-items: flex-start; margin-bottom: 35px; z-index: 2; transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .node-item.pending { opacity: 0.3; filter: grayscale(100%); }
    .node-item.pending .node-icon { background: #1e293b; border: 2px solid #334155; color: #64748b; }
    .node-item.completed .node-icon { background: #1e293b; border: 2px solid #475569; color: #f8fafc; }
    .node-item.waiting .node-icon { background: #f59e0b; border: 2px solid #fbbf24; color: #fff; box-shadow: 0 0 15px rgba(245, 158, 11, 0.5); }
    
    @keyframes pulse-ring {
        0% { transform: scale(0.8); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
        100% { transform: scale(0.8); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
    }
    .node-item.active .node-icon {
        background-color: var(--accent);
        border: 2px solid #60a5fa; color: white;
        animation: pulse-ring 2s infinite;
        transform: scale(1.1);
    }
    .node-icon {
        width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
        margin-right: 20px; font-size: 11px; font-weight: 800; font-family: monospace; transition: all 0.3s;
    }
    .node-content h4 { margin: 0 0 6px 0; font-size: 15px; font-weight: 600; color: #f1f5f9; letter-spacing: 0.5px; }
    .node-content p { margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5; }

    /* Export Bar */
    .export-bar {
        background: var(--panel); backdrop-filter: blur(10px);
        padding: 18px 24px; border-radius: 16px; border: 1px solid var(--panel-border);
        margin-top: 20px; display: flex; align-items: center; justify-content: space-between;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"session_{uuid.uuid4()}"
config = {"configurable": {"thread_id": st.session_state.thread_id}}


@st.cache_resource
def get_cached_graph():
    return build_research_graph()


app = get_cached_graph()


def render_timeline(current_node):
    nodes = [
        {"id": "Planner", "n": "1", "t": "Topic Deconstruction", "d": "Splitting topic into core sub-questions."},
        {"id": "Screener", "n": "2", "t": "Literature Screening", "d": "Retrieving and filtering high-impact papers."},
        {"id": "Reader", "n": "3", "t": "Deep Reading", "d": "Concurrent parsing and grounded retrieval reasoning."},
        {"id": "DataMiner", "n": "4", "t": "Quantitative Mining", "d": "Structured metrics extraction from evidence."},
        {"id": "Writer", "n": "5", "t": "Manuscript Drafting", "d": "Synthesizing insights into an academic draft."},
        {"id": "Reviewer", "n": "6", "t": "Peer Review", "d": "Citation and grounding audit before release."},
        {"id": "Editor", "n": "7", "t": "AI Revisions", "d": "Interactive post-editing with user feedback."},
    ]
    html = '<div class="timeline-wrapper">'
    found_active = False
    for node in nodes:
        status = "active" if node["id"] == current_node else (
            "completed" if not found_active and current_node != "Completed" else "pending"
        )
        if current_node == "Completed":
            status = "completed"
        if current_node == "Suspended" and node["id"] == "Screener":
            status = "waiting"
        if node["id"] == current_node:
            found_active = True
        html += (
            f'<div class="node-item {status}"><div class="node-icon">{node["n"]}</div>'
            f'<div class="node-content"><h4>{node["t"]}</h4><p>{node["d"]}</p></div></div>'
        )
    return html + "</div>"


def format_draft_with_tooltips(draft_text):
    pattern = r'\[来源:\s*(.*?),\s*原文:\s*"(.*?)"\]'

    def replace_match(match):
        source_id = escape(match.group(1))
        quote = escape(match.group(2))
        return f'<span class="citation-tooltip" data-tooltip="原文提取：{quote}">[Ref: {source_id}]</span>'

    return re.sub(pattern, replace_match, draft_text)


def generate_latex(draft_text):
    clean_text = re.sub(r'\[来源:.*?\]', '', draft_text)
    return f"""\\documentclass[12pt, a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{geometry}}
\\usepackage{{hyperref}}
\\geometry{{margin=1in}}
\\title{{Literature Review Synthesis}}
\\author{{DeepScholar AI Agent}}
\\date{{\\today}}
\\begin{{document}}
\\maketitle
{clean_text}
\\end{{document}}"""


def build_summary_cards(state_values):
    candidate_papers = state_values.get("candidate_papers", [])
    selected_papers = state_values.get("selected_papers", [])
    extracted_insights = state_values.get("extracted_insights", [])
    quantitative_data = state_values.get("quantitative_data", [])
    revision_count = state_values.get("revision_count", 0)
    return f"""
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-label">Candidates</div><div class="stat-value">{len(candidate_papers)}</div><div class="stat-helper">全网初筛回来的候选文献</div></div>
        <div class="stat-card"><div class="stat-label">Selected</div><div class="stat-value">{len(selected_papers)}</div><div class="stat-helper">进入精读管线的论文</div></div>
        <div class="stat-card"><div class="stat-label">Insights</div><div class="stat-value">{len(extracted_insights)}</div><div class="stat-helper">围绕子问题沉淀的洞察</div></div>
        <div class="stat-card"><div class="stat-label">Review Loop</div><div class="stat-value">{revision_count}</div><div class="stat-helper">{len(quantitative_data)} 条结构化指标已提取</div></div>
    </div>
    """


def render_status_banner(current_state, is_suspended):
    if not current_state.values:
        return '<div class="status-banner"><strong>Status:</strong> Awaiting a research topic to start the pipeline.</div>'
    if is_suspended:
        return '<div class="status-banner"><strong>Status:</strong> Human review required before literature screening continues.</div>'
    if current_state.values.get("draft"):
        return '<div class="status-banner"><strong>Status:</strong> Draft completed. You can export it or continue with revision instructions below.</div>'
    if current_state.next:
        next_nodes = ", ".join(current_state.next)
        return f'<div class="status-banner"><strong>Status:</strong> Workflow ready to continue at {escape(next_nodes)}.</div>'
    return '<div class="status-banner"><strong>Status:</strong> Pipeline initialized.</div>'


def process_graph(input_data, timeline_placeholder, details_placeholder):
    for output in app.stream(input_data, config=config):
        for node_name, _ in output.items():
            timeline_placeholder.markdown(render_timeline(node_name), unsafe_allow_html=True)
            with details_placeholder.container():
                st.markdown(
                    (
                        "<div class='status-banner' style='margin-top:14px;'>"
                        f"<strong>Live Step:</strong> {escape(node_name)} is running."
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
            time.sleep(0.2)


current_state = app.get_state(config)
is_suspended = bool(current_state.next and "Screener" in current_state.next)

with st.sidebar:
    st.markdown("<h3>Initialize Task</h3>", unsafe_allow_html=True)
    topic = st.text_area(
        "RESEARCH TOPIC",
        value="Large language models for grounded academic review",
        height=120,
    )
    start_btn = st.button("RUN PIPELINE", use_container_width=True)
    sidebar_hitl_placeholder = st.empty()

st.markdown(
    """
    <div class="hero-panel">
        <div class="hero-kicker">Research Workflow Studio</div>
        <h1 class="hero-title">DeepScholar</h1>
        <p class="hero-subtitle">A multi-stage academic agent for planning, screening, reading, mining evidence, drafting, reviewing, and revising literature synthesis with human checkpoints.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(build_summary_cards(current_state.values or {}), unsafe_allow_html=True)
st.markdown(render_status_banner(current_state, is_suspended), unsafe_allow_html=True)

col1, col2 = st.columns([1.05, 2.35], gap="large")

with col1:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        "<p style='color: #8A7E72; font-size: 11px; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>Agent Orchestration</p>",
        unsafe_allow_html=True,
    )
    timeline_placeholder = st.empty()
    details_placeholder = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown(
        "<p style='color: #8A7E72; font-size: 11px; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>Synthesis Report</p>",
        unsafe_allow_html=True,
    )
    draft_placeholder = st.empty()
    export_placeholder = st.empty()
    chat_placeholder = st.container()

if st.session_state.get("should_resume", False):
    st.session_state.should_resume = False
    draft_placeholder.markdown(
        "<div class='academic-draft-container' style='text-align:center;'><br>Resuming orchestration...</div>",
        unsafe_allow_html=True,
    )
    with st.spinner("Resuming..."):
        process_graph(None, timeline_placeholder, details_placeholder)
    st.rerun()

if not current_state.values:
    timeline_placeholder.markdown(render_timeline("Pending"), unsafe_allow_html=True)
    draft_placeholder.markdown(
        "<div class='academic-draft-container' style='text-align:center; color:#A09588; padding:100px 0;'>Awaiting task initialization.</div>",
        unsafe_allow_html=True,
    )
elif is_suspended:
    timeline_placeholder.markdown(render_timeline("Suspended"), unsafe_allow_html=True)
    draft_placeholder.markdown(
        "<div class='academic-draft-container' style='text-align:center; color:#A09588; padding:100px 0;'>System paused. Awaiting human approval in the sidebar.</div>",
        unsafe_allow_html=True,
    )
elif current_state.values.get("draft"):
    timeline_placeholder.markdown(render_timeline("Completed"), unsafe_allow_html=True)
    final_draft = current_state.values["draft"]
    html_draft = format_draft_with_tooltips(final_draft)
    draft_placeholder.markdown(
        f"<div class='academic-draft-container'>{html_draft}</div>",
        unsafe_allow_html=True,
    )

    with export_placeholder.container():
        st.markdown("<div class='export-bar'>", unsafe_allow_html=True)
        col_txt, col_md, col_tex = st.columns([3, 1, 1])
        with col_txt:
            st.markdown(
                "<span style='font-size: 13px; color: #8A7E72; font-weight: 600;'>EXPORT MANUSCRIPT</span>",
                unsafe_allow_html=True,
            )
        with col_md:
            st.download_button(
                label="Markdown",
                data=final_draft,
                file_name="review.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_tex:
            st.download_button(
                label="LaTeX",
                data=generate_latex(final_draft),
                file_name="review.tex",
                mime="text/plain",
                use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with chat_placeholder:
        st.markdown(
            "<hr style='border:0; border-top:1px solid #E0D7CB; margin:30px 0 15px 0;'>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color: #8A7E72; font-size: 11px; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>Assistant Revisions</p>",
            unsafe_allow_html=True,
        )
        for msg in current_state.values.get("chat_history", []):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_input := st.chat_input("Instruct the AI to revise, expand, or format..."):
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.spinner("Agent is revising..."):
                process_graph({"user_feedback": user_input}, timeline_placeholder, details_placeholder)
            st.rerun()

if start_btn:
    st.session_state.thread_id = f"session_{uuid.uuid4()}"
    config["configurable"]["thread_id"] = st.session_state.thread_id
    sidebar_hitl_placeholder.empty()
    timeline_placeholder.markdown(render_timeline("Planner"), unsafe_allow_html=True)
    draft_placeholder.markdown(
        "<div class='academic-draft-container' style='text-align:center;'><br>Orchestrating agents...</div>",
        unsafe_allow_html=True,
    )
    with st.spinner("Executing..."):
        process_graph(create_initial_state(research_topic=topic), timeline_placeholder, details_placeholder)
    st.rerun()

if is_suspended:
    with sidebar_hitl_placeholder.container():
        st.markdown(
            (
                "<div style='background-color:#FCFAEF; border:1px dashed #C19A6B; border-radius:12px; "
                "padding:15px; margin-top:15px;'><h4 style='color:#A67B5B; margin:0 0 5px 0; font-size:14px;'>"
                "Human-in-the-Loop</h4><p style='font-size:11px; color:#8A7E72; margin:0;'>"
                "Review and refine the generated sub-questions before continuing.</p></div>"
            ),
            unsafe_allow_html=True,
        )
        q_text = "\n".join(current_state.values.get("sub_questions", []))
        edited_q = st.text_area("EDIT QUESTIONS:", value=q_text, height=180)
        if st.button("CONFIRM & RESUME", type="primary", use_container_width=True):
            app.update_state(
                config,
                {"sub_questions": [q.strip() for q in edited_q.split("\n") if q.strip()]},
            )
            st.session_state.should_resume = True
            st.rerun()
