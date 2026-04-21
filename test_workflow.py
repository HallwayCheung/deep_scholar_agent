# test_workflow_day7.py
import os
import json
from workflow.state import ResearchState
from workflow.state import create_initial_state
from workflow.nodes import planner_node, screener_node
from workflow.nodes import reader_node  # 确保导入了新写的节点

def run_manual_workflow_test():
    # 确保填入了 API Key
    if os.getenv("DASHSCOPE_API_KEY") is None:
        print("❌ 警告: 未检测到 DASHSCOPE_API_KEY 环境变量，请确保已设置。")
        # 如果你之前在 node.py 里硬编码了，这里可以忽略

    print("=" * 50)
    print("🚀 启动模拟工作流测试 (Day 7: Planner -> Screener)")
    print("=" * 50)

    # 1. 初始化全局状态 (State)
    # 这就是最初始的“白板”，只有用户的原始课题
    current_state: ResearchState = create_initial_state("大语言模型在医疗领域的幻觉消除技术")

    print(f"📌 初始输入: 用户的研究课题为 [{current_state['research_topic']}]")

    # =========================================
    # 模拟 LangGraph 步骤 1：执行 Planner 节点
    # =========================================
    print("\n>>> 正在唤醒 Planner 节点...")
    # 将当前的白板递给 Planner
    planner_update = planner_node(current_state)

    # 模拟 LangGraph 的状态更新机制：将 Planner 的产出合并到全局白板中
    current_state.update(planner_update)

    print("\n📊 Planner 节点执行后的 State 状态 (节选):")
    print(json.dumps({"sub_questions": current_state["sub_questions"]}, indent=2, ensure_ascii=False))

    # =========================================
    # 模拟 LangGraph 步骤 2：执行 Screener 节点
    # =========================================
    print("\n>>> 正在唤醒 Screener 节点...")
    # 将更新后的白板递给 Screener
    screener_update = screener_node(current_state)

    # 模拟状态更新
    current_state.update(screener_update)

    print("\n📊 Screener 节点执行后的 State 状态 (节选):")
    # 打印最终被选中的高质量论文
    for idx, paper in enumerate(current_state["selected_papers"], 1):
        print(f"  [{idx}] 标题: {paper['title']}")

    print("\n" + "=" * 50)
    print("✅ 测试完成！数据在这两个节点间成功流转。")
    print("=" * 50)

    # =========================================
    # 模拟 LangGraph 步骤 3：执行 Reader 节点
    # =========================================

    print("\n>>> 正在唤醒 Reader (精读员) 节点...")
    # 将包含子问题和优选论文的白板递给 Reader
    reader_update = reader_node(current_state)

    # 【重点说明】：因为这里是我们手写的模拟脚本，我们需要手动模拟 operator.add 的追加效果
    # 在真正的 LangGraph 框架里，这行代码框架会自动帮你做
    current_state["extracted_insights"].extend(reader_update["extracted_insights"])

    print("\n📊 Reader 节点执行后的 State 状态 (节选):")
    for idx, insight in enumerate(current_state["extracted_insights"], 1):
        print(f"--- 洞察 {idx} ---")
        print(insight)

    print("\n" + "=" * 50)
    print("successful")
    print("=" * 50)

if __name__ == "__main__":
    run_manual_workflow_test()
