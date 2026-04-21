# core/vector_db.py
import chromadb


class LocalPaperDB:
    def __init__(self, db_path="./workspace/chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name="papers")

    def add_chunks(self, chunks: list, paper_id: str | None = None):
        """将切好的 Markdown 块存入向量库。"""
        if not chunks:
            return

        documents = [chunk["text"] for chunk in chunks]
        metadatas = [{"paper_id": chunk["paper_id"], "section": chunk["header"]} for chunk in chunks]
        ids = [
            f"{chunk['paper_id']}_chunk_{index}"
            for index, chunk in enumerate(chunks)
        ]

        self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        label = paper_id or "mixed_batch"
        print(f"💾 成功将 {label} 的 {len(chunks)} 个数据块灌入 ChromaDB！")

    def search(self, query: str, top_k: int = 4) -> str:
        """真实检索并拼接为 Agent 认识的格式"""
        results = self.collection.query(query_texts=[query], n_results=top_k)

        if not results['documents'] or not results['documents'][0]:
            return "未检索到相关文献片段。"

        observation_text = ""
        for i in range(len(results['documents'][0])):
            chunk_text = results['documents'][0][i]
            paper_id = results['metadatas'][0][i].get("paper_id", "Unknown_ID")

            observation_text += f"\n检索结果 {i + 1}:\n[Paper_ID: {paper_id}]\n原文: \"{chunk_text}\"\n" + "-" * 20

        return observation_text

    def verify_quote_exists(self, paper_id: str, quote: str, threshold: float = 0.5) -> bool:
        """用基于词汇重合度的模糊匹配校验引用原文是否存在。"""
        if paper_id == "None":
            return True

        results = self.collection.get(where={"paper_id": paper_id})
        documents = results.get("documents", [])
        
        quote_words = set(quote.replace(".", "").replace(",", "").lower().split())
        if not quote_words:
            return True

        for document in documents:
            doc_words = set(document.replace(".", "").replace(",", "").lower().split())
            intersection = quote_words.intersection(doc_words)
            if len(intersection) / len(quote_words) >= threshold:
                return True

        return False
