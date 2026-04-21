import re
from typing import Dict, List, Tuple

from openai import OpenAI


class GroundedReActAgent:
    def __init__(self, api_key: str, local_db, model: str = "qwen-plus"):
        self.db = local_db
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
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
2. Final Answer 中的每一个事实陈述，必须挂载严格的引用标签。
3. 引用格式标准为：[来源: Paper_ID, 原文: "提取的精确原文片段"]。
4. 绝对不允许捏造本地数据库中不存在的观点或文献ID。

【特别提醒】：由于本地数据库存储的是全英文文献片段，当你在执行 `SearchLocalDB` 时，`Action Input` 提供的搜索关键词必须是【英文关键字】（例如使用 "object detection" 而非 "目标检测"），否则将无法查找到任何资料！
"""

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=1000,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            return f"Error: LLM 调用失败 - {exc}"

    def _parse_action(self, text: str) -> Tuple[str | None, str | None]:
        action_match = re.search(r"Action:\s*(.*?)(?:\n|$)", text)
        input_match = re.search(r"Action Input:\s*(.*?)(?:\n|$)", text)
        action = action_match.group(1).strip() if action_match else None
        action_input = input_match.group(1).strip() if input_match else None
        return action, action_input

    def _verify_citations(self, answer_text: str) -> Tuple[bool, str]:
        citation_pattern = r"\[来源:\s*(.*?),\s*原文:\s*\"(.*?)\"\]"
        citations = re.findall(citation_pattern, answer_text)

        if not citations:
            return False, "未能检测到标准格式的引用标签。"

        for paper_id, quote in citations:
            clean_paper_id = paper_id.replace("Paper_ID:", "").strip()
            if not quote.strip():
                return False, f"引用 {clean_paper_id} 缺失原文片段内容。"
            if hasattr(self.db, "verify_quote_exists") and clean_paper_id != "None":
                if not self.db.verify_quote_exists(clean_paper_id, quote):
                    return False, f"引用的原文在论文 {clean_paper_id} 中不存在。"

        return True, ""

    def run(self, query: str, max_steps: int = 4) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.append({"role": "user", "content": f"我的研究问题是: {query}"})

        print(f"\n🚀 开始执行 Grounded-ReAct 分析任务: {query}")

        for step in range(1, max_steps + 1):
            print(f"\n[Step {step}/{max_steps}] 等待大模型思考...")
            response_text = self._call_llm(messages)
            print(f"\n🤖 Agent 输出:\n{response_text}")
            messages.append({"role": "assistant", "content": response_text})

            if "Final Answer:" in response_text:
                final_answer = response_text.split("Final Answer:")[-1].strip()
                is_valid, error_msg = self._verify_citations(final_answer)
                if is_valid:
                    print("\n✅ 拦截器校验通过。")
                    return final_answer
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "System Error: 你的最终答案未通过校验。"
                            f"原因：{error_msg}。请严格按照要求重新生成带有正确引用格式的 Final Answer。"
                        ),
                    }
                )
                continue

            action, action_input = self._parse_action(response_text)
            if action == "SearchLocalDB" and action_input:
                search_results = self.db.search(action_input)
                observation = f"Observation:\n{search_results}"
                print(observation)
                messages.append({"role": "user", "content": observation})
            elif action == "None":
                messages.append({"role": "user", "content": "请基于已有证据输出 Final Answer。"})
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": "System Error: 未检测到有效的 Action 格式，请继续推进任务。",
                    }
                )

        return '经过检索，本地精选文献库中并未提及关于此问题的相关信息。[来源: None, 原文: "无"]'
