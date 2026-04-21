# test_rag_search.py
from tools.search_engine import SemanticScholarSearcher
import json


def main():
    # 实例化我们的搜索引擎
    searcher = SemanticScholarSearcher()

    # 假设用户的研究课题
    topic = "Multimodal Autonomous Driving"

    # 获取前 5 篇（为了测试看得很清楚，先只拿 5 篇）
    results = searcher.search_papers(query=topic, limit=5)

    # 打印结果看看
    for idx, paper in enumerate(results, 1):
        print(f"\n[{idx}] 标题: {paper['title']}")
        print(f"    年份: {paper['year']} | 引用量: {paper['citation_count']}")
        print(f"    PDF链接: {paper['pdf_url']}")
        # 摘要太长，截断显示前 100 个字符
        abstract_snippet = paper['abstract'][:100] + "..." if paper['abstract'] else "无摘要"
        print(f"    摘要片段: {abstract_snippet}")


if __name__ == "__main__":
    main()