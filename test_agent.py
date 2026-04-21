import os
import re

from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Dict, Tuple

load_dotenv()
# ==========================================
# 1. 模拟数据库 (Mock DB)
# ==========================================
class MockLocalDB:
    """伪造一个本地向量数据库，专门返回固定的医学 LLM 相关文献片段"""

    def search(self, query: str) -> str:
        print(f"\n   [MockDB 收到检索请求] -> 关键词: '{query}'")
        # 无论搜什么，我们都返回这两个伪造的片段，模拟 RAG 召回的数据
        return """
        检索结果 1:
        [Paper_ID: MedLLM_2023_A]
        原文: "在医疗领域应用大语言模型时，幻觉问题尤为致命。我们提出了一种基于医学知识图谱（Medical Knowledge Graph）的后处理修正机制（Post-processing Correction Mechanism），将特定实体的幻觉率降低了45%。"

        检索结果 2:
        [Paper_ID: MedLLM_2023_B]
        原文: "现有的 RAG 技术在处理复杂病历时，检索出的片段往往缺乏上下文连贯性。实验表明，引入长文本注意力机制以及检索前的 Query 重写，可以缓解这一问题。"
        """


# ==========================================
# 2. 防幻觉 Agent 核心 (接入 Qwen)
# ==========================================
class GroundedReActAgent:
    def __init__(self, api_key: str, local_db):
        self.db = local_db
        # 接入 Qwen 兼容接口
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

        # 极其严苛的 System Prompt
        self.system_prompt = """
        你是一个严谨的学术助理。你的任务是基于本地数据库解答用户的学术问题。

        【工作流规范】：
        你必须严格遵循以下思考过程进行交互：
        Thought: 思考我接下来需要做什么。
        Action: 必须是 `SearchLocalDB` 或者 `None`（当你有足够信息回答时）。
        Action Input: 提供给工具的检索关键词。
        Observation: 工具返回的真实数据片段（你不能自己生成 Observation，必须等待系统返回）。

        【学术红线（绝对遵守）】：
        1. 当你收集到足够信息准备回答时，必须以 "Final Answer: " 开头。
        2. Final Answer 中的每一个事实陈述，**必须**挂载严格的引用标签。
        3. 引用格式标准为：[来源: Paper_ID, 原文: "提取的精确原文片段"]。
        4. 绝对不允许捏造本地数据库中不存在的观点或文献ID。
        """

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """调用通义千问 API"""
        try:
            response = self.client.chat.completions.create(
                model="qwen-plus",  # 使用 qwen-plus 模型
                messages=messages,
                temperature=0.1,  # 极低温度，保证输出稳定严谨
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: LLM 调用失败 - {str(e)}"

    def _parse_action(self, text: str) -> Tuple[str, str]:
        """解析 Action 和 Action Input"""
        action_match = re.search(r"Action:\s*(.*?)(?:\n|$)", text)
        input_match = re.search(r"Action Input:\s*(.*?)(?:\n|$)", text)

        action = action_match.group(1).strip() if action_match else None
        action_input = input_match.group(1).strip() if input_match else None
        return action, action_input

    def _verify_citations(self, answer_text: str) -> Tuple[bool, str]:
        """核心：正则校验引用格式"""
        citation_pattern = r"\[来源:\s*(.*?),\s*原文:\s*\"(.*?)\"\]"
        citations = re.findall(citation_pattern, answer_text)

        if not citations:
            return False, "未能检测到标准格式的引用标签。必须在每一句事实陈述后加上 [来源: Paper_ID, 原文: \"...\"]。"

        for paper_id, quote in citations:
            if not quote.strip():
                return False, f"引用 {paper_id} 缺失原文片段内容。"

        return True, ""

    def run(self, query: str, max_steps: int = 4) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.append({"role": "user", "content": f"我的研究问题是: {query}"})

        print(f"\n🚀 开始执行 Grounded-ReAct 分析任务: {query}")
        print("-" * 50)

        for step in range(1, max_steps + 1):
            print(f"\n[Step {step}/{max_steps}] 等待大模型思考...")
            response_text = self._call_llm(messages)
            print(f"\n🤖 Agent 输出:\n{response_text}")

            messages.append({"role": "assistant", "content": response_text})

            # 拦截 Final Answer
            if "Final Answer:" in response_text:
                final_answer = response_text.split("Final Answer:")[-1].strip()
                is_valid, error_msg = self._verify_citations(final_answer)

                if is_valid:
                    print("\n✅ 拦截器校验通过！完美生成带引用的学术回答。")
                    return final_answer
                else:
                    print(f"\n⚠️ 拦截器触发！原因: {error_msg}")
                    print("   -> 正在强制打回，要求大模型重写...")
                    correction_prompt = f"System Error: 你的最终答案未通过校验。原因：{error_msg}。请严格按照要求重新生成带有正确引用格式的 Final Answer。"
                    messages.append({"role": "user", "content": correction_prompt})
                    continue

            # 执行工具
            action, action_input = self._parse_action(response_text)

            if action == "SearchLocalDB":
                search_results = self.db.search(action_input)
                observation = f"Observation: \n{search_results}"
                print(observation)
                messages.append({"role": "user", "content": observation})
            elif action == "None":
                messages.append({"role": "user", "content": "请输出 Final Answer。"})
            else:
                messages.append(
                    {"role": "user", "content": "System Error: 未检测到有效的 Action 格式，请检查你的输出格式。"})

        return "Final Answer: 经过检索，本地精选文献库中并未提及关于此问题的相关信息。[来源: None, 原文: \"无\"]"


# ==========================================
# 3. 运行测试
# ==========================================
if __name__ == "__main__":
    # 替换为你的真实 API Key
    # 强烈建议在终端中先执行 export DASHSCOPE_API_KEY="你的key"
    API_KEY = os.getenv("DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY")

    if API_KEY == "YOUR_DASHSCOPE_API_KEY":
        print("❌ 请先在代码中填入你的 DashScope API Key！")
        exit(1)

    # 1. 初始化伪造数据库
    mock_db = MockLocalDB()

    # 2. 初始化 Agent
    agent = GroundedReActAgent(api_key=API_KEY, local_db=mock_db)

    # 3. 提出一个非常具体的问题
    test_query = "目前的文献中，如何解决大语言模型在医疗领域的幻觉问题？"

    # 4. 运行 Agent
    final_result = agent.run(test_query)

    print("\n" + "=" * 50)
    print("🎯 最终交付给用户的回答:")
    print(final_result)
    print("=" * 50)