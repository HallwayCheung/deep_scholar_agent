import chromadb
import re

class LocalPaperDB:
    def __init__(self):
        # 持久化存储在本地
        self.client = chromadb.PersistentClient(path="./workspace/chroma_db")
        self.collection = self.client.get_or_create_collection(name="papers")

    def add_chunks(self, chunks: list, paper_id: str):
        """将语义块灌入 ChromaDB，必须绑定 Metadata"""
        documents = [chunk["text"] for chunk in chunks]
        # 这里的 metadata 是防幻觉的关键！
        metadatas = [{"paper_id": paper_id, "section": chunk["header"]} for chunk in chunks]
        ids = [f"{paper_id}_chunk_{i}" for i in range(len(chunks))]

        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ {paper_id} 的 {len(chunks)} 个语义块已入库！")


def chunk_markdown(md_text: str, paper_id: str) -> list:
    """基于 Markdown 标题树的语义切块器"""
    # 按照 Markdown 标题 (如 # Intro, ## Methods) 进行分割
    sections = re.split(r'(^#+\s+.*)', md_text, flags=re.MULTILINE)

    chunks = []
    current_header = "Abstract/General"

    for text in sections:
        text = text.strip()
        if not text:
            continue

        # 如果是标题行，更新当前上下文
        if re.match(r'^#+\s+', text):
            current_header = text
        else:
            # 如果是内容段落，将其与标题打包成一个 Chunk
            chunk_content = f"{current_header}\n{text}"
            chunks.append({
                "header": current_header,
                "text": chunk_content,
                "paper_id": paper_id
            })

    print(f"🧩 文献 {paper_id} 已被切分为 {len(chunks)} 个语义块。")
    return chunks