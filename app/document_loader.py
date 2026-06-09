import os
from typing import List, Dict
from pypdf import PdfReader
from docx import Document


def read_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def read_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text


def read_docx(file_path: str) -> str:
    doc = Document(file_path)
    text = ""

    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"

    return text


def load_document(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".txt":
        return read_txt(file_path)

    if ext == ".pdf":
        return read_pdf(file_path)

    if ext == ".docx":
        return read_docx(file_path)

    raise ValueError(f"Không hỗ trợ định dạng file: {ext}")


def extract_metadata_from_text(content: str, file_name: str) -> Dict:
    metadata = {
        "title": os.path.splitext(file_name)[0],
        "source": "Nguồn do quản trị viên cung cấp",
        "period": "Chưa phân loại",
        "url": ""
    }

    lines = content.splitlines()

    for line in lines[:15]:
        line = line.strip()

        if line.startswith("TIÊU ĐỀ:"):
            metadata["title"] = line.replace("TIÊU ĐỀ:", "").strip()

        elif line.startswith("NGUỒN:"):
            metadata["url"] = line.replace("NGUỒN:", "").strip()

        elif line.startswith("TÊN NGUỒN:"):
            metadata["source"] = line.replace("TÊN NGUỒN:", "").strip()

        elif line.startswith("GIAI ĐOẠN:"):
            metadata["period"] = line.replace("GIAI ĐOẠN:", "").strip()

    return metadata


def split_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def load_documents_from_folder(folder_path: str) -> List[Dict]:
    """
    Đọc toàn bộ tài liệu trong folder_path, bao gồm cả thư mục con.
    Ví dụ:
    data/web_documents/baotanglichsu/*.txt
    data/web_documents/nlv/*.txt
    data/manual_documents/*.pdf
    """
    documents = []

    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)

            try:
                content = load_document(file_path)

                if not content or not content.strip():
                    print(f"Bỏ qua file rỗng: {file_path}")
                    continue

                metadata = extract_metadata_from_text(content, file_name)

                documents.append({
                    "title": metadata["title"],
                    "file_name": file_name,
                    "file_path": file_path,
                    "content": content,
                    "source": metadata["source"],
                    "period": metadata["period"],
                    "url": metadata["url"]
                })

            except Exception as e:
                print(f"Lỗi đọc file {file_path}: {e}")

    return documents