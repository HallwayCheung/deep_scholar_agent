import chromadb
import re

class LocalPaperDB:
    def __init__(self):
        # Persistent local storage
        self.client = chromadb.PersistentClient(path="./workspace/chroma_db")
        self.collection = self.client.get_or_create_collection(name="papers")

    def add_chunks(self, chunks: list, paper_id: str):
        """Ingest semantic chunks into ChromaDB; must bind Metadata."""
        documents = [chunk["text"] for chunk in chunks]
        # Metadata is the key to preventing hallucinations!
        metadatas = [{"paper_id": paper_id, "section": chunk["header"]} for chunk in chunks]
        ids = [f"{paper_id}_chunk_{i}" for i in range(len(chunks))]

        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ {paper_id} 的 {len(chunks)} 个语义块已入库！")


def chunk_markdown(md_text: str, paper_id: str) -> list:
    """Semantic chunker based on Markdown header trees."""
    # Split according to Markdown headers (e.g. # Intro, ## Methods)
    sections = re.split(r'(^#+\s+.*)', md_text, flags=re.MULTILINE)

    chunks = []
    current_header = "Abstract/General"

    for text in sections:
        text = text.strip()
        if not text:
            continue

        # If it is a header line, update the current context
        if re.match(r'^#+\s+', text):
            current_header = text
        else:
            # If it is a content paragraph, bundle it with the header into a Chunk
            chunk_content = f"{current_header}\n{text}"
            chunks.append({
                "header": current_header,
                "text": chunk_content,
                "paper_id": paper_id
            })

    print(f"🧩 文献 {paper_id} 已被切分为 {len(chunks)} 个语义块。")
    return chunks