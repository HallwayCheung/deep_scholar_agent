# workflow/nodes.py
import concurrent
import json
import os
import re
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from workflow.state import ResearchState
from tools.search_engine import SemanticScholarSearcher
from tools.pdf_parser import AcademicPDFParser
from core.chunker import chunk_markdown
from core.vector_db import LocalPaperDB
from core.grounded_react import GroundedReActAgent

load_dotenv()
API_KEY = os.getenv("DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY")
llm_client = OpenAI(
    api_key=API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# def call_qwen(prompt: str) -> str:
#     """通用的 Qwen 调用辅助函数"""
#     response = llm_client.chat.completions.create(
#         model="qwen-plus",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.3
#     )
#     return response.choices[0].message.content
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_qwen(prompt: str) -> str:
    """通用的 Qwen 调用辅助函数 (具备自动重试能力)"""
    try:
        response = llm_client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"   ⚠️ [API 波动] 大模型调用出错: {e}，正在准备自动重试...")
        raise e # 必须把异常抛出，tenacity 才能捕获并触发重试

# ==========================================
# 节点 1：Planner (规划师)
# ==========================================
def planner_node(state: ResearchState) -> Dict[str, Any]:
    """
    将宏观课题拆解为 3-4 个具体的子问题。
    """
    topic = state.get("research_topic", "").strip()
    print(f"\n[节点执行] 👷 Planner 正在拆解课题: {topic}")

    prompt = f"""
    你是一个资深科研导师。学生的研究课题是："{topic}"。
    任务1：为了写出高质量综述，将该课题拆解为 3 个最核心的具体子问题（必须是【简体中文】）。
    任务2：使用 Mermaid.js 的 `graph TD` 语法构建一个该课题的“全景概念拓扑树”。必须包含最少 3-4 层节点深度，节点之间要有包含和分支关系。节点文字要求【简体中文】。
    
    注意：你只允许输出一个合法的 JSON 数据（不要用 markdown codeblock 包含），格式如下：
    {{
        "sub_questions": ["问题1", "问题2", "问题3"],
        "concept_map": "graph TD\\n A[课题名称] --> B[子方向1]\\n B --> C[核心技术1]\\n ..."
    }}
    绝对不要输出任何其他废话。
    """

    response = call_qwen(prompt)

    try:
        clean_json = response.strip("`").replace("json\n", "").replace("JSON\n", "").strip()
        data = json.loads(clean_json)
        sub_questions = data.get("sub_questions", [])
        concept_map = data.get("concept_map", "graph TD\\n A[暂无图谱数据]")
    except Exception as e:
        print(f"⚠️ Planner 解码 JSON 失败: {e}")
        sub_questions = [f"关于 {topic} 的主流方法是什么？", f"{topic} 当前存在哪些挑战？", f"{topic} 的评估指标有哪些？"]
        concept_map = "graph TD\\n A[解析错误]"

    print(f"✅ Planner 拆解完毕: {sub_questions}")
    return {
        "sub_questions": sub_questions, 
        "concept_map": concept_map,
        "logs": [f"👷 Planner: 成功将课题拆解为 {len(sub_questions)} 个核心维度，并构建了结构化概念雷达。"]
    }


# ==========================================
# 节点 2：Screener (初筛员)
# ==========================================
def screener_node(state: ResearchState) -> Dict[str, Any]:
    """【真实版】初筛员：接入 Semantic Scholar 真实 API 获取数据"""
    print(f"\n[节点执行] 🧐 Screener 正在全网检索真实文献...")
    topic = state.get("research_topic", "")
    min_papers = state.get("min_papers", 5)

    # 取出 2-3 个英文关键词用于搜索引擎
    query_prompt = f"Please extract 2 to 4 key English words from this topic for a paper search engine. Only output the English keywords, nothing else: '{topic}'"
    search_query = call_qwen(query_prompt).replace('"', '').replace("'", "").strip()
    print(f"  -> 🔍 关键词提纯完毕: '{search_query}' (原课题: {topic})")
    logs = [f"🧐 Screener: 关键词提纯完成 -> '{search_query}'"]

    # 1. 唤醒你的真实搜索引擎
    searcher = SemanticScholarSearcher()
    real_candidate_papers = searcher.search_papers(query=search_query, limit=min_papers * 2)
    
    # 🔵 Phase 7: 注入本地文献
    local_docs = state.get("local_documents", [])
    if local_docs:
        logs.append(f"📂 Screener: 检测到 {len(local_docs)} 份用户上传的本地文献，已并入初选集。")
        for ld in local_docs:
            real_candidate_papers.insert(0, {
                "paper_id": ld["id"],
                "title": ld["title"],
                "abstract": ld.get("abstract", ""),
                "is_local": True,
                "citation_count": 999 
            })

    selected_papers = []
    logs.append(f"🔍 Screener: 正在对 {len(real_candidate_papers)} 篇潜在文献进行深度语义打分与相关性评估...")

    # 2. 用大模型对摘要进行打分
    for paper in real_candidate_papers:
        if not paper.get('abstract'):
            continue

        eval_prompt = f"评估此论文摘要与课题'{topic}'相关性(1-10分纯数字)：\n标题:{paper['title']}\n摘要:{paper['abstract'][:500]}"
        score_str = call_qwen(eval_prompt).strip()

        try:
            score = int(re.search(r'\d+', score_str).group()) if re.search(r'\d+', score_str) else 0
            if score >= 7 or paper.get("is_local"):
                selected_papers.append(paper)
                print(f"  🟢 [得分 {score}] 保留: {paper['title'][:50]}...")
            else:
                print(f"  🔴 [得分 {score}] 剔除: {paper['title'][:50]}...")
        except Exception:
            continue

        if len(selected_papers) >= min_papers + (len(local_docs) if local_docs else 0):
            break

    if not selected_papers:
        selected_papers = real_candidate_papers[:min_papers]

    logs.append(f"✅ Screener: 筛选完成。已筛选出 {len(selected_papers)} 篇待研读文献。")
    return {
        "candidate_papers": real_candidate_papers, 
        "selected_papers": selected_papers,
        "logs": logs
    }


# def reader_node(state: ResearchState) -> Dict[str, Any]:
#     print(f"\n[节点执行] 📚 Reader 启动重型管线：高并发下载、解析与深度推理...")
#
#     parser = AcademicPDFParser()
#     db = LocalPaperDB()
#     agent = GroundedReActAgent(api_key=API_KEY, local_db=db)
#
#     print("  -> 📥 阶段一：启动线程池，并发处理精选文献...")
#
#     # --- 核心提速代码开始 ---
#     def process_single_paper(paper):
#         """定义单个线程需要完成的完整流水线"""
#         pdf_url = paper.get("pdf_url")
#         paper_id = paper.get("paper_id")
#
#         if not pdf_url or not paper_id:
#             return None
#
#         print(f"     [线程启动] 正在后台处理文献: {paper_id}...")
#         try:
#             # 1. 下载 PDF
#             pdf_path = parser.download_pdf(pdf_url, paper_id)
#             if not pdf_path:
#                 return None
#
#             # 2. 解析 Markdown
#             md_text = parser.parse_to_markdown(pdf_path, paper_id)
#             if not md_text:
#                 return None
#
#             # 3. 切块
#             chunks = chunk_markdown(md_text, paper_id)
#             return {"paper_id": paper_id, "chunks": chunks}
#         except Exception as e:
#             print(f"     ❌ [线程错误] 处理 {paper_id} 失败: {e}")
#             return None
#
#     # 启用线程池，max_workers 设为 5（因为我们最多精读 5 篇）
#     all_paper_chunks = []
#     with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#         # 将任务分发给多个线程同时执行！
#         futures = [executor.submit(process_single_paper, p) for p in state["selected_papers"]]
#
#         # 收集所有线程的处理结果
#         for future in concurrent.futures.as_completed(futures):
#             result = future.result()
#             if result and result["chunks"]:
#                 all_paper_chunks.extend(result["chunks"])
#                 print(f"     ✅ [线程完成] 文献 {result['paper_id']} 解析完毕！")
#
#     # 为了避免 ChromaDB 在多线程下因 SQLite 锁引发报错，我们等所有线程跑完后，统一单线程安全入库
#     if all_paper_chunks:
#         print(f"  -> 💾 正在将所有线程汇总的 {len(all_paper_chunks)} 个数据块安全灌入 ChromaDB...")
#         # 注意：这里需要你稍微调整一下 db.add_chunks，让它能接收混合了不同 paper_id 的 chunks 列表
#         # 或者直接用一个 for 循环按 paper_id 分组入库
#         db.add_chunks(all_paper_chunks, "Batch_Insert")
#         # --- 核心提速代码结束 ---
#
#     print("  -> 🧠 阶段二：防幻觉微内核启动，针对子问题深度检索...")
#     extracted_insights = []
#     for idx, question in enumerate(state["sub_questions"], 1):
#         print(f"\n    [微内核] 正在攻克子问题 {idx}/{len(state['sub_questions'])}: {question}")
#
#         # 你的死循环 ReAct 开始在真实的几十页文献数据中翻找！
#         answer = agent.run(question)
#
#         insight = f"【关于 '{question}' 的洞察】\n{answer}\n"
#         extracted_insights.append(insight)
#
#     return {"extracted_insights": extracted_insights}

def data_miner_node(state: ResearchState) -> Dict[str, Any]:
    """
    数据挖掘员：原生Function Calling 智能体。
    强制大模型将文本中的定量指标提取为结构化 JSON。
    """
    print(f"\n[节点执行] 📊 DataMiner 正在使用原生 Function Calling 提取定量数据...")

    insights_text = "\n".join(state.get("extracted_insights", []))
    if not insights_text.strip():
        return {"quantitative_data": []}

    # 1. 定义大模型可以调用的工具 (纯原生 JSON Schema 协议)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "save_literature_matrix",
                "description": "当在文本中发现文献的综合学术信息时，调用此函数保存多维度的结构化对比矩阵数据。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "matrix_entries": {
                            "type": "array",
                            "description": "提取的学术跨维矩阵列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "paper_method": {"type": "string", "description": "核心架构或提出的方法名称"},
                                    "datasets": {"type": "string", "description": "验证所用数据集表述"},
                                    "key_metrics": {"type": "string", "description": "最核心的量化表现指标数值"},
                                    "limitations": {"type": "string", "description": "该方法的局限性或存在的路线争议点"}
                                },
                                "required": ["paper_method", "datasets", "key_metrics", "limitations"]
                            }
                        }
                    },
                    "required": ["matrix_entries"]
                }
            }
        }
    ]

    # 2. 构建消息并强制发起 Tool Calling
    messages = [
        {"role": "system",
         "content": "你是一个严谨的数据分析师。请阅读提供的研究洞察，提取所有明确的定量指标。你必须调用 `save_metrics_table` 工具来输出结果。"},
        {"role": "user", "content": f"待提取文本：\n{insights_text}"}
    ]

    try:
        # 3. 调用 API，注意传入了 tools 参数
        response = llm_client.chat.completions.create(
            model="qwen-plus",
            messages=messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "save_literature_matrix"}}  # 强制它调用
        )

        response_message = response.choices[0].message

        # 4. 手动解析 Tool Call 回调
        if response_message.tool_calls:
            print("   🟢 成功拦截到学术矩阵矩阵封装请求！")
            tool_call = response_message.tool_calls[0]
            function_args = json.loads(tool_call.function.arguments)
            extracted_metrics = function_args.get("matrix_entries", [])
        else:
            print("   ⚠️ 模型未能正确发起工具调用。尝试正则回退兜底解析...")
            content = response_message.content or ""
            match = re.search(r'```(?:json)?(.*?)```', content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            try:
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    clean_content = content[json_start:json_end]
                    extracted_metrics = json.loads(clean_content).get("matrix_entries", [])
                else:
                    extracted_metrics = json.loads(content).get("matrix_entries", [])
            except:
                extracted_metrics = []

        if extracted_metrics:
            print(f"   📊 成功结构化提取了 {len(extracted_metrics)} 条全维度学术矩阵！")
            for m in extracted_metrics:
                print(f"      - [{m.get('paper_method')}] 指标: {m.get('key_metrics')}")
                
        # 追加执行：领域黑话字典提取 (Jargon Buster)
        print("   🔍 正在提取核心学术黑话，构建领域解密字典...")
        jargon_prompt = f"分析以下文本，提取出 最核心的 5 到 8 个学术「暗语」、高频缩写或极其专业的领域词汇。要求对每个词给出极短的直白中文解释（适合小白看懂）。\n文本: {insights_text}\n请直接返回合法的 JSON 数组，如: [{{\"term\": \"mAP\", \"definition\": \"平均精度均值，衡量目标检测准度的终极指标\"}}]"
        jargons = []
        try:
            jargon_res = call_qwen(jargon_prompt).strip("`").replace("json\n", "").strip()
            jargons = json.loads(jargon_res)
            print(f"   📘 提取了 {len(jargons)} 条核心术语字典！")
        except:
            print("   ⚠️ 字典提取回落失败。")

        return {
            "quantitative_data": extracted_metrics, 
            "jargon_dictionary": jargons,
            "logs": [f"📊 DataMiner: 成功从文献深度挖掘并结构化了 {len(extracted_metrics)} 条核心学术矩阵，并构建了 {len(jargons)} 条领域术语库。"]
        }
    except Exception as e:
        print(f"   ❌ DataMiner 提取失败: {e}")
        return {
            "quantitative_data": [], 
            "jargon_dictionary": [],
            "logs": [f"⚠️ DataMiner: 尝试提取结构化数据时出现偏差: {str(e)}"]
        }

def reader_node(state: ResearchState) -> Dict[str, Any]:
    print(f"\n[节点执行] 📚 Reader 启动重型管线：高并发下载、解析与深度推理...")
    logs = ["📚 Reader: 启动防幻觉研读管线..."]

    parser = AcademicPDFParser()
    db = LocalPaperDB()
    agent = GroundedReActAgent(api_key=API_KEY, local_db=db)
    selected_papers = state.get("selected_papers", [])
    sub_questions = state.get("sub_questions", [])
    local_docs_map = {d["id"]: d for d in state.get("local_documents", [])}

    if not selected_papers:
        return {
            "extracted_insights": ["【系统提示】当前没有可精读的文献。"],
            "logs": ["⚠️ Reader: 未发现待精读文献，流程暂停。"]
        }

    # 🔴 核心：定义单个线程的处理逻辑
    def process_single_paper(paper):
        paper_id = paper.get("paper_id")
        if not paper_id: return None
        
        # 📂 Phase 7: 处理本地上传的 Bypass
        if paper.get("is_local") and paper_id in local_docs_map:
            print(f"     [本地入库] 正在跳过下载，直接转换本地文献: {paper_id}")
            text_content = local_docs_map[paper_id]["content"]
            # 我们复用块切分逻辑
            chunks = chunk_markdown(text_content, paper_id)
            return chunks

        pdf_url = paper.get("pdf_url")
        if not pdf_url: return None

        try:
            # 1. 下载真实 PDF
            pdf_path = parser.download_pdf(pdf_url, paper_id)
            if not pdf_path: return None
            # 2. 视觉库暴力解析 Markdown
            md_text = parser.parse_to_markdown(pdf_path, paper_id)
            # 3. 正则语义切块
            chunks = chunk_markdown(md_text, paper_id)
            return chunks
        except Exception as e:
            print(f"     ❌ [线程错误] 处理 {paper_id} 失败: {e}")
            return None

    logs.append(f"📥 Reader: 正在并发解析 {len(selected_papers)} 篇文献（包含本地与云端）...")
    all_paper_chunks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(selected_papers))) as executor:
        futures = [executor.submit(process_single_paper, paper) for paper in selected_papers]
        for future in concurrent.futures.as_completed(futures):
            chunks = future.result()
            if chunks: all_paper_chunks.extend(chunks)

    if all_paper_chunks:
        logs.append(f"💾 Reader: 已将 {len(all_paper_chunks)} 个高价值知识切片存入本地向量数据库。")
        db.add_chunks(all_paper_chunks)

    print("  -> 🧠 阶段二：防幻觉微内核启动...")
    extracted_insights = []
    logs.append(f"🧠 Reader: 开始多轮 RAG 深度检索，正在攻克 {len(sub_questions)} 个核心科研子问题...")

    for idx, question in enumerate(sub_questions, 1):
        print(f"\n    [微内核] 攻克子问题 {idx}/{len(sub_questions)}: {question}")
        answer = agent.run(question)
        extracted_insights.append(f"【关于 '{question}' 的洞察】\n{answer}\n")

    logs.append("✅ Reader: 循证阅读阶段结束，已沉淀深度学术洞察。")
    return {
        "extracted_insights": extracted_insights,
        "logs": logs
    }


def writer_node(state: ResearchState) -> Dict[str, Any]:
    """主笔：整合信息，生成最终带有严格引用的中文学术草稿"""
    print(f"\n[节点执行] ✍️ Writer 正在撰写学术综述草稿...")

    insights = state.get("extracted_insights", [])
    quantitative_data = state.get("quantitative_data", [])
    review_comments = state.get("review_comments", "")
    topic = state.get("research_topic", "该研究主题")

    insights_text = "\n".join(insights)
    data_text = str(quantitative_data) if quantitative_data else "无定量数据"

    # 🔴 核心修复：把占位符写得更明确，防止大模型照抄
    prompt = f"""
    You are an expert academic writer. Your task is to write a comprehensive, rigorous literature review based ONLY on the provided insights and quantitative data.
    
    The user's original topic language determines your output language. 
    Topic: {topic}
    (If the topic is in Chinese, you MUST write the final manuscript entirely in Chinese. If the topic is in English, write in English, etc.)

    [Inputs]
    1. Sub-questions & Insights:
    {insights_text}
    2. Quantitative Data Miners:
    {quantitative_data}

    [Strict Rules]
    1. Write a structured academic synthesis (Introduction, Methods/Trends, Findings, Conclusion).
    2. ANY claim made MUST include an inline citation formatted exactly as [来源: Paper_ID, 原文: "exact quote excerpt"]. If you don't have a source, do NOT state the claim.
    3. 引用标签的格式严格为：[来源: 真实的字母数字ID, 原文: "EXACT_QUOTE"]  <- 注意：直接写ID即可，绝对不要包含"Paper_ID:"字样！
    4. 致命警告：标签中的 `原文` 部分必须原封不动复制参考资料原文。
    5. 【学术演进对比表】：强制要求！你必须利用 Quantitative Data Miners 提取的多维数据，在正文合适位置使用 Markdown 语法绘制一张《核心研究方法对比矩阵》表格（涵盖:架构方法、验证数据集、核心指标、局限性）。
    6. 【争议与路线批判】：强制要求！必须单开一节《主流技术路线争议与批判 (Critical Debates and Discrepancies)》，在其中深入对比不同文献之间的路线抵触点、模型劣势、或者评估争议，必须显得具备研究生级别的反思与审视。

    示例正确写法：
    与传统方法相比，该模型在收敛速度上表现更优 [来源: 07e5b88d29c5, 原文: "The proposed model converges significantly faster."]。

    请严格遵循以上规则，开始撰写：
    """

    try:
        draft = call_qwen(prompt)

        # ---> 【新增功能：后置拼装正式的独立参考文献表】 <---
        reference_section = "\n\n### 参考文献 (References)\n"
        used_papers = state.get("selected_papers", [])
        if used_papers:
            for idx, p in enumerate(used_papers, 1):
                authors = f" (Cited Count: {p.get('citation_count', 0)})"
                year = p.get('year') or "N/A"
                ref_id = p.get('paper_id')
                reference_section += f"{idx}. **{p.get('title')}** ({year}){authors} - *Ref_ID: {ref_id}*\n"
        else:
            reference_section += "1. 本文自动生成，因缺少候选文献，暂无参考文献库映射。\n"
        
        # 将参考文献附加到草稿末尾
        draft += reference_section
        
        print("✅ Writer 撰写完成了附带官方参考库的初稿！")
        return {
            "draft": draft,
            "logs": ["✍️ Writer: 已完成长篇学术综述初稿的撰写，包含结构化章节、参考文献表及溯源引用。"]
        }
    except Exception as e:
        print(f"   ❌ Writer 生成失败: {e}")
        return {
            "draft": "",
            "logs": [f"⚠️ Writer: 综述初稿生成遇到挑战: {str(e)}"]
        }


def reviewer_node(state: ResearchState) -> Dict[str, Any]:
    """
    同行评审员（终极防线升级版）：Semantic Reverse RAG (语义反向校验)。
    提取引用标签，从本地召回原始英文 Chunk，利用 LLM 进行跨语言的语义逻辑核查。
    """
    print(f"\n[节点执行] 🕵️‍♂️ Reviewer 启动 Semantic Reverse RAG 校验机制...")

    draft = state.get("draft", "")
    revision_count = state.get("revision_count", 0)

    if revision_count >= 3:
        print("   ⚠️ 达到最大重写次数，强制放行...")
        return {
            "review_comments": "PASS",
            "draft": "> ⚠️ **系统警告**：部分引用未能通过语义核查，存在幻觉风险，请读者自行核实。\n\n" + draft
        }

    # 1. 提取引用标签：[来源: XXX, 原文: "YYY"]
    pattern = r'\[来源:\s*(.*?),\s*原文:\s*"(.*?)"\]'
    citations = re.findall(pattern, draft)

    if not citations:
        print("   ❌ 格式错误：未检测到 [来源: ID, 原文: \"...\"] 标签。")
        return {"review_comments": "请务必在每一处事实后添加 [来源: Paper_ID, 原文: \"具体原文段落\"]。",
                "revision_count": revision_count + 1}

    print(f"   🔍 扫描到 {len(citations)} 处引用，正在进行跨语言语义核查...")

    from core.vector_db import LocalPaperDB
    db = LocalPaperDB()
    hallucinations_found = []

    # 2. 遍历引用，进行“语义反向检查”
    for paper_id, quoted_text in citations:
        clean_paper_id = paper_id.replace("Paper_ID:", "").replace("paper_id:", "").replace("Paper_ID", "").strip()
        quoted_text = quoted_text.strip()

        if "none" in clean_paper_id.lower() or not clean_paper_id:
            print("      ▶ 检测到无引用声明，启动事实断言判定器...")
            judge_claim_prompt = f"""
            Is the following sentence a specific scientific claim, a metric, or a finding that MUST require a citation?
            If it contains specific claims that should be backed by literature, output ONLY: REQUIRED
            If it is just a transitional sentence, general introduction, or common knowledge, output ONLY: OPTIONAL
            Sentence: {quoted_text}
            """
            claim_check = call_qwen(judge_claim_prompt)
            if "REQUIRED" in claim_check.upper():
                msg = f"驳回：该断言缺少文献支撑 -> '{quoted_text}'"
                print(f"         ❌ {msg}")
                hallucinations_found.append(msg)
            else:
                print("         ✅ 通过：过渡性/常识性语句，允许无引用。")
            continue

        print(f"      ▶ 正在核查文献 [{clean_paper_id}] 的声明...")

        try:
            # 🔴 这里一定要用 clean_paper_id 去查数据库！
            db_results = db.collection.get(where={"paper_id": clean_paper_id})
            original_chunks = db_results.get("documents", [])

            if not original_chunks:
                msg = f"本地库不存在文献 ID '{clean_paper_id}'"
                print(f"         ❌ {msg}")
                hallucinations_found.append(msg)
                continue

            is_fuzzy_match = db.verify_quote_exists(clean_paper_id, quoted_text, threshold=0.5)

            if is_fuzzy_match:
                print(f"         ✅ 通过：引用片段字面模糊匹配成功")
                continue

            # 若字面匹配度不足，不直接判死刑，启动大模型语义支撑裁判
            print("         ⚠️ 字面匹配度不足，启动 LLM 跨语言语义支撑裁判...")
            full_original_text = " ".join(original_chunks)

            # 3. 🚀 核心升级：跨语言语义校验 Prompt (LLM-as-a-Judge)
            # 截取前 4000 个字符防止超 Token，通常足够验证
            judge_prompt = f"""你是一个极其严格的学术核查机器。
            请判断【待核查的声明】是否能被【真实的文献原文】在语义上完全支撑（允许翻译、总结或概括，但不能凭空捏造数据或事实）。

            【真实的文献原文】:
            {full_original_text[:4000]}

            【待核查的声明】:
            {quoted_text}

            如果原文能支撑该声明，请仅输出：PASS
            如果原文无法支撑、或者数据对不上，请仅输出：FAIL
            """

            # 这里调用你的大模型生成函数
            judge_result = call_qwen(judge_prompt)

            if "FAIL" in judge_result.upper():
                msg = f"文献 {paper_id} 的真实原文无法支持您的声明：'{quoted_text}'"
                print(f"         ❌ 驳回：声明与原文语义不符 (幻觉/过度翻译)")
                hallucinations_found.append(msg)
            else:
                print(f"         ✅ 通过：LLM裁判认定语义逻辑吻合")

        except Exception as e:
            print(f"      ⚠️ 查询异常: {e}")

    # 4. 决断流转
    if hallucinations_found:
        error_msg = "【发现引用幻觉】\n" + "\n".join(hallucinations_found) + "\n请根据真实数据修正，禁止凭借固有记忆编造！"
        print(f"   🚨 拦截成功！打回重写。")
        return {
            "review_comments": error_msg, 
            "revision_count": revision_count + 1,
            "logs": [f"🕵️‍♂️ Reviewer: ⚠️ 检测到 {len(hallucinations_found)} 处引用偏差，已打回重写以确保严谨性。"]
        }
    else:
        print("   🎉 全部校验通过！草稿严谨度达到学术标准。")
        return {
            "review_comments": "PASS",
            "logs": ["🕵️‍♂️ Reviewer: ✅ 深度语义核查通过。所有引用标签均已在原文中成功溯源，未发现幻觉。"]
        }


def editor_node(state: ResearchState) -> Dict[str, Any]:
    """编辑员：根据人类的反馈指令，结合上下文修改草稿。"""
    print("\n[节点执行] 📝 Editor 正在根据您的指令修改草稿...")

    feedback = state.get("user_feedback", "")
    current_draft = state.get("draft", "")
    history = state.get("chat_history", [])
    topic = state.get("research_topic", "")

    # 构建包含上下文的 Prompt
    prompt = f"""你是一位资深的学术主笔。用户对当前的文献综述草稿提出了修改意见。

    【研究主题】：
    {topic}

    【当前草稿内容】：
    {current_draft}

    【用户的修改指令】：
    {feedback}

    请执行以下两项任务：
    1. 严格按照用户的指令对草稿进行修改、扩写或删减。
    2. 给用户写一句简短的回复（例如："已为您在第二段补充了对抗鲁棒性的对比数据。"）

    请必须以如下 JSON 格式返回：
    {{
        "assistant_reply": "你对用户说的简短回复",
        "revised_draft": "修改后的完整 Markdown 草稿内容"
    }}
    """

    try:
        # 这里的 call_qwen 替换为你实际的大模型调用代码，记得要求返回 JSON
        response_text = call_qwen(prompt)

        # 简单清理一下可能的 markdown 代码块标记
        cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(cleaned_text)

        new_draft = result.get("revised_draft", current_draft)
        reply = result.get("assistant_reply", "已完成修改。")

        # 组装新的聊天记录
        new_history = history.copy()
        new_history.append({"role": "user", "content": feedback})
        new_history.append({"role": "assistant", "content": reply})

        print(f"   💬 Editor 回复: {reply}")

        # 🔴 返回更新后的草稿、新的历史记录，并清空本次的 feedback 以防重复触发
        return {
            "draft": new_draft,
            "chat_history": new_history,
            "user_feedback": "",
            "logs": [f"📝 Editor: 已响应用户反馈，完成文稿的针对性修补。"]
        }

    except Exception as e:
        print(f"   ❌ Editor 修改失败: {e}")
        return {
            "chat_history": history + [
                {"role": "user", "content": feedback},
                {"role": "assistant", "content": "这次修改没有成功解析，我保留了原稿，请再试一次更具体的指令。"},
            ],
            "user_feedback": "",
            "logs": [f"⚠️ Editor: 指令解析异常: {str(e)}"]
        }


# ==========================================
# 节点 6：Critic (批判性审视智能体 - Phase 6)
# ==========================================
def critic_node(state: ResearchState) -> Dict[str, Any]:
    """
    批判性思维注入：作为"科研红队"，对已生成的综述提出 3-5 个深刻的质疑性问题，
    帮助初学者识别该领域潜在的坑、局限性和争议点。
    """
    print(f"\n[节点执行] 🔴 Critic 正在进行红队批判分析...")

    draft = state.get("draft", "")
    topic = state.get("research_topic", "")
    insights = "\n".join(state.get("extracted_insights", []))

    if not draft:
        return {"critical_checklist": []}

    prompt = f"""
    You are a world-class academic critic with deep expertise. You have read the following literature review on "{topic}" and want to challenge the research community with pointed, thought-provoking questions.

    [Literature Review Draft]
    {draft[:4000]}

    [Raw Insights from Papers]
    {insights[:2000]}

    Your task: Generate exactly 5 critical, "Red Team" style checklist items. These should:
    - Identify specific limitations, assumptions, or biases in the reviewed methods
    - Point out what is NOT being discussed enough (missing perspectives)
    - Challenge over-hyped claims with skeptical questions
    - Highlight real-world applicability gaps
    - Be written in Chinese (since our users are Chinese researchers)

    Return ONLY a valid JSON array (no markdown code blocks). Format:
    [
        {{
            "category": "方法论局限",
            "question": "当前主流方法是否在 X 场景下过拟合？文献是否充分讨论了跨域泛化能力？",
            "severity": "high"
        }},
        ...
    ]
    severity must be: "high", "medium", or "low".
    """

    try:
        raw = call_qwen(prompt).strip().strip("`").replace("json\n", "").replace("JSON\n", "").strip()
        # Find JSON array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            checklist = json.loads(raw[start:end])
        else:
            checklist = []
        print(f"   🔴 批判分析完成，生成了 {len(checklist)} 条红队问题！")
        return {
            "critical_checklist": checklist,
            "logs": ["🔴 Critic: 已完成“科研红队”深度压力测试，通过 5 个批判维度透视领域局限。"]
        }
    except Exception as e:
        print(f"   ❌ Critic 分析失败: {e}")
        return {
            "critical_checklist": [],
            "logs": [f"⚠️ Critic: 批判性思维注入失败: {str(e)}"]
        }
