# main.py
import os
from dotenv import load_dotenv
from workflow.graph import build_research_graph
from workflow.state import create_initial_state

load_dotenv()

def main():
    # 确保 API Key 已就位
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("❌ 请先设置 DASHSCOPE_API_KEY 环境变量！")
        return

    # 1. 获取编译好的智能体团队 (App)
    research_app = build_research_graph()

    # 2. 定义初始输入
    # 这是用户的原始诉求，图引擎会自动把它转化为 ResearchState 格式
    initial_input = create_initial_state("who is adam?")


    # 🔴 关键修改：为这次任务分配一个唯一的“线程 ID”
    # 如果代码中断，下次运行只要使用相同的 thread_id，就会从断点继续跑！
    config = {"configurable": {"thread_id": "research_task_001"}}

    print("\n" + "=" * 50)
    print("🚀 启动 DeepScholar 自动化科研引擎")
    print("=" * 50)

    # 3. 一键启动！(invoke 会自动按照我们画的图，从头跑到尾)
    final_state = research_app.invoke(initial_input,config=config)

    print("\n" + "=" * 50)
    print("🎉 全流程执行完毕！最终生成的学术综述草稿如下：")
    print("=" * 50)

    # 直接打印 Writer 生成的 draft，而不是循环打印 extracted_insights
    if "draft" in final_state and final_state["draft"]:
        print(final_state["draft"])
    else:
        print("⚠️ 未能生成有效草稿。")


if __name__ == "__main__":
    main()
