import requests
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

class ArxivFallbackSearcher:
    """备用的 ArXiv 论文搜索引擎，在主搜索引擎熔断时紧急接管。"""
    def search_papers(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        print(f"🔄 检测到 Semantic Scholar 请求受限/失败，正在无缝切换备用检索引擎 (ArXiv)...")
        # 净化并格式化 arxiv 专用搜索字符串
        clean_query = query.replace("\n", " ").replace("\r", " ")
        words = [word for word in clean_query.split() if word]
        
        # 为了防止提纯词过多导致 ArXiv 严格匹配查不到东西（比如查不到 5 篇），设定多级松弛查询
        query_strategies = [
            "+AND+".join(words),               # 1. 严格全匹配
            "+AND+".join(words[:4]),           # 2. 截断前4个核心词
            "+AND+".join(words[:2])            # 3. 极速兜底前2个核心词
        ]
        
        for strategy in query_strategies:
            if not strategy:
                continue
                
            url = f"http://export.arxiv.org/api/query?search_query=all:{strategy}&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending"
            try:
                response = requests.get(url, timeout=12)
                response.raise_for_status()
                
                root = ET.fromstring(response.text)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                
                valid_papers = []
                for entry in root.findall('atom:entry', ns):
                    title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
                    summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
                    published = entry.find('atom:published', ns).text[:4]
                    paper_id = entry.find('atom:id', ns).text.split('/')[-1]
                    
                    pdf_url = entry.find('atom:id', ns).text.replace('abs', 'pdf') + ".pdf"
                    
                    valid_papers.append({
                        "paper_id": f"arxiv-{paper_id}",
                        "title": title,
                        "year": published,
                        "citation_count": 0,
                        "abstract": summary,
                        "pdf_url": pdf_url
                    })
                    
                # 如果这个策略拿到的文章数量超过了阈值的哪怕一半，我们也认为可以交差
                if len(valid_papers) >= limit // 2 or len(valid_papers) >= 3:
                    print(f"✅ ArXiv 备用管线成功拦截并获取 {len(valid_papers)} 篇文献！（命中策略：{strategy}）")
                    return valid_papers
                    
            except Exception as e:
                print(f"⚠️ ArXiv 策略 {strategy} 获取失败: {e}")
                
        print(f"❌ 备用检索引擎穷尽了所有松弛查询仍未获取到足够文献。")
        # 强行返回最后一次拿到的（可能只有1篇）
        return valid_papers if 'valid_papers' in locals() else []

class SemanticScholarSearcher:
    def __init__(self):
        # 使用基于相关性排序的原生端点
        self.base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        self.fallback = ArxivFallbackSearcher()

    def search_papers(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        根据关键词搜索论文，使用相关性排序，带有重试机制和断崖备用管线。
        """
        # 洗掉大模型生成的冗余换行符，防止破坏 HTTP URL
        clean_query = query.replace("\n", " ").replace("\r", " ").strip()
        print(f"🔍 正在 Semantic Scholar 检索课题: '{clean_query}'...")

        fields = "paperId,title,abstract,citationCount,year,openAccessPdf"
        params = {
            "query": clean_query,
            "limit": limit * 2,
            "fields": fields,
            "year": "2020-"
        }

        # 加入带有指数退避的简易自愈重试逻辑
        for attempt in range(2):
            try:
                response = requests.get(self.base_url, params=params, timeout=10)
                
                if response.status_code == 429:
                    print(f"⚠️ 触发并发限制 (429 Too Many Requests)，正在挂起降额 3 秒重试... (次尝试 {attempt+1}/2)")
                    time.sleep(3)
                    continue

                response.raise_for_status()
                data = response.json()

                if "data" not in data or not data["data"]:
                    print("⚠️ Semantic Scholar 未找到相关领域的最新高相关论文。")
                    return self.fallback.search_papers(clean_query, limit=limit)

                raw_papers = data["data"]
                valid_papers = []

                for paper in raw_papers:
                    if paper.get("openAccessPdf") and paper["openAccessPdf"].get("url"):
                        cleaned_paper = {
                            "paper_id": paper.get("paperId"),
                            "title": paper.get("title"),
                            "year": paper.get("year"),
                            "citation_count": paper.get("citationCount", 0),
                            "abstract": paper.get("abstract"),
                            "pdf_url": paper["openAccessPdf"]["url"]
                        }
                        valid_papers.append(cleaned_paper)

                    if len(valid_papers) >= limit:
                        break

                print(f"✅ 主力引擎成功获取 {len(valid_papers)} 篇具备公开 PDF 的文献！")
                
                # 如果主力引擎因为 PDF 缺失导致可用文献为 0，依然切备用
                if not valid_papers:
                    return self.fallback.search_papers(clean_query, limit=limit)
                    
                return valid_papers

            except requests.exceptions.RequestException as e:
                print(f"❌ Semantic Scholar API 请求异常: {e}")
                # 出现超时或严重报错，直接熔断并走备用引擎
                return self.fallback.search_papers(clean_query, limit=limit)
                
        # 重试结束仍失败
        return self.fallback.search_papers(clean_query, limit=limit)