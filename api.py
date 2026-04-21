import uuid
import json
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from workflow.graph import build_research_graph
from workflow.state import create_initial_state

load_dotenv()

app = FastAPI(title="DeepScholar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize graph singleton
research_app = build_research_graph()

def format_sse(data: dict) -> str:
    # Handle non-serializable elements if needed, but defaults should be fine.
    # Convert anything complex to string.
    try:
        return f"data: {json.dumps(data)}\n\n"
    except Exception:
        # Fallback dump
        return f"data: {json.dumps(str(data))}\n\n"

@app.post("/api/research")
async def start_research(request: Request):
    """
    Starts or resumes research workflow and streams graph events using Server-Sent Events.
    """
    body = await request.json()
    topic = body.get("topic", "")
    feedback = body.get("feedback", "")
    thread_id = body.get("thread_id")
    
    if not thread_id:
        thread_id = f"session_{uuid.uuid4()}"
        
    config = {"configurable": {"thread_id": thread_id}}
    
    current_state = research_app.get_state(config)
    
    # Decide input based on current state
    if not current_state.values:
        min_papers = body.get("min_papers", 5)
        input_data = create_initial_state(research_topic=topic, min_papers=int(min_papers))
    else:
        # Human in the loop / Feedback logic
        sub_questions = body.get("sub_questions")
        selected_paper_ids = body.get("selected_paper_ids") # Phase 8: Paper Review HITL
        
        if sub_questions:
            research_app.update_state(config, {"sub_questions": sub_questions})
            input_data = None
        elif selected_paper_ids is not None:
            # Filter candidate papers based on user selection
            candidates = current_state.values.get("candidate_papers", [])
            selected = [p for p in candidates if p["paper_id"] in selected_paper_ids]
            research_app.update_state(config, {"selected_papers": selected})
            input_data = None
        elif feedback:
            input_data = {"user_feedback": feedback}
        else:
            input_data = None
            
    def event_generator():
        try:
            # FastAPI's StreamingResponse runs standard generators in a threadpool, 
            # so this blocking synchronous graph stream is safe.
            for output in research_app.stream(input_data, config=config, stream_mode="updates"):
                for node_name, state_update in output.items():
                    current = research_app.get_state(config)
                    
                    # 🔴 Phase 8: 提取节点日志进行即时推送 (Thought Streaming)
                    latest_logs = state_update.get("logs", [])
                    for log in latest_logs:
                        yield format_sse({
                            "type": "thought",
                            "content": log,
                            "node": node_name
                        })

                    # 推送完整状态更新以供前端同步 UI
                    yield format_sse({
                        "type": "state_update",
                        "node": node_name,
                        "thread_id": thread_id,
                        "state_values": current.values,
                        "next_nodes": list(current.next) if current.next else []
                    })
        except Exception as e:
            yield format_sse({"error": str(e), "node": "Error"})
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/state/{thread_id}")
async def get_state(thread_id: str):
    """Fetch current state of a thread."""
    config = {"configurable": {"thread_id": thread_id}}
    current_state = research_app.get_state(config)
    return {
        "values": current_state.values,
        "next": list(current_state.next) if current_state.next else []
    }

@app.post("/api/copilot")
async def ask_copilot(request: Request):
    """
    Independent Copilot endpoint. Answers user questions strictly based on the generated manuscript and insights.
    Does NOT mutate the LangGraph state. Streams the answer back.
    """
    body = await request.json()
    thread_id = body.get("thread_id")
    message = body.get("message", "")
    
    config = {"configurable": {"thread_id": thread_id}}
    current_state = research_app.get_state(config)
    
    draft = current_state.values.get("draft", "") if current_state.values else ""
    insights = "\n".join(current_state.values.get("extracted_insights", [])) if current_state.values else ""
    
    from workflow.nodes import llm_client
    
    prompt = f"""
    You are an academic Copilot helping a beginner understand the following literature review draft.
    You must answer the user's question with simple, easily understandable analogies in Chinese.
    Do NOT rewrite the draft. Just answer the question.
    
    [Draft Context]
    {draft[:3000]} # Limit to core context
    
    [Detailed Insights]
    {insights[:2000]}
    
    User Question: {message}
    """
    
    def stream_copilot():
        try:
            response = llm_client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield format_sse({"token": chunk.choices[0].delta.content})
        except Exception as e:
            yield format_sse({"error": str(e)})
            
    return StreamingResponse(stream_copilot(), media_type="text/event-stream")

@app.post("/api/upload_pdf")
async def upload_pdf(file: UploadFile = File(...), thread_id: str = Form(...)):
    """
    Phase 7: Local Bring Your Own PDF (BYOPDF) Integration
    Uploads a PDF, extracts text using PyMuPDF, and saves it into the LangGraph state.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    try:
        import fitz  # PyMuPDF
        
        # Read file content
        content = await file.read()
        
        # Extract text using PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        text_content = ""
        for page in doc:
            text_content += page.get_text() + "\n"
            
        doc.close()
        
        # Update State
        config = {"configurable": {"thread_id": thread_id}}
        current_state = research_app.get_state(config)
        
        # Create initial state if not exist
        if not current_state.values:
            from workflow.state import create_initial_state
            # Create a placeholder topic
            initial_data = create_initial_state(research_topic="BYOPDF Local Upload", min_papers=5)
            research_app.update_state(config, initial_data)
            current_state = research_app.get_state(config)
            
        local_docs = current_state.values.get("local_documents", [])
        
        new_doc = {
            "title": file.filename,
            "abstract": text_content[:1500] + "...",  # treat first part as abstract for screening
            "content": text_content,
            "id": f"local_{uuid.uuid4().hex[:8]}"
        }
        
        # Push into state
        local_docs.append(new_doc)
        research_app.update_state(config, {"local_documents": local_docs})
        
        return {
            "success": True, 
            "doc_id": new_doc["id"], 
            "message": f"Parsed {len(text_content)} characters from {file.filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/discovery")
async def manual_discovery(request: Request):
    """
    Phase 7: Manual Discovery Button Logic
    Triggers the Screener again with a specialized prompt to find new hot topics.
    """
    body = await request.json()
    thread_id = body.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}
    current_state = research_app.get_state(config)
    
    if not current_state.values:
        raise HTTPException(status_code=400, detail="Thread not found")
        
    topic = current_state.values.get("research_topic", "")
    discovery_input = {
        "user_feedback": f"Please perform a fresh discovery search for the latest high-impact papers in '{topic}' from the last 12 months. Focus on breakthrough results.",
        "logs": ["⚡ Discovery: 用户手动触发实时追踪，正在扫描全球学术数据库中的最新突破..."]
    }
    
    def discovery_stream():
        # We force run from Screener or provide feedback to Editor? 
        # For simplicity, we trigger a specific sub-flow or just update state and stream.
        try:
            # Here we just use the research_app but we might want to target specific nodes.
            # But let's just use the main flow with feedback.
            for output in research_app.stream(discovery_input, config=config, stream_mode="updates"):
                for node_name, state_update in output.items():
                    current = research_app.get_state(config)
                    latest_logs = state_update.get("logs", [])
                    for log in latest_logs:
                        yield format_sse({"type": "thought", "content": log, "node": node_name})
                    yield format_sse({
                        "type": "state_update", 
                        "node": node_name, 
                        "state_values": current.values,
                        "next_nodes": list(current.next) if current.next else []
                    })
        except Exception as e:
            yield format_sse({"error": str(e)})

    return StreamingResponse(discovery_stream(), media_type="text/event-stream")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
