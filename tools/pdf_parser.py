import os

import pymupdf4llm
import requests
from tenacity import retry, stop_after_attempt, wait_fixed


class AcademicPDFParser:
    def __init__(self, workspace_dir: str = "workspace"):
        self.workspace_dir = workspace_dir
        os.makedirs(self.workspace_dir, exist_ok=True)

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(3))
    def download_pdf(self, pdf_url: str, paper_id: str) -> str:
        """从开放链接下载 PDF，失败时自动重试。"""
        if not pdf_url:
            return ""

        print(f"     [下载器] 尝试下载文献: {paper_id} ...")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/pdf",
            }
            response = requests.get(pdf_url, headers=headers, timeout=15)
            response.raise_for_status()

            file_path = os.path.join(self.workspace_dir, f"{paper_id}.pdf")
            with open(file_path, "wb") as file_obj:
                file_obj.write(response.content)
            return file_path
        except requests.exceptions.Timeout:
            print(f"     ❌ [下载超时] {paper_id} 响应过慢，准备重试。")
            raise
        except Exception as exc:
            print(f"     ❌ [下载失败] {paper_id}: {exc}")
            raise

    def parse_to_markdown(self, pdf_path: str, paper_id: str) -> str:
        """将 PDF 转为 Markdown，并保留调试用备份。"""
        if not os.path.exists(pdf_path):
            return ""

        print(f"⚙️ 正在解析 PDF 到 Markdown: {paper_id}...")
        try:
            md_text = pymupdf4llm.to_markdown(pdf_path)
            md_path = os.path.join(self.workspace_dir, f"{paper_id}.md")
            with open(md_path, "w", encoding="utf-8") as file_obj:
                file_obj.write(md_text)
            return md_text
        except Exception as exc:
            print(f"❌ 解析失败 {pdf_path}: {exc}")
            return ""
