"""Load course PDFs into a single Chroma collection.

    data/lecture/*.pdf   -> source="lecture"
    data/textbook/*.pdf  -> source="textbook"

Run: python -m tutor.ingest
"""
import re

import chromadb
from pypdf import PdfReader

from tutor.config import CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION, DATA_DIR, SOURCES


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        # Prefer to break at a sentence boundary in the back half of the window.
        if end < len(text):
            cut = text.rfind(". ", start + size // 2, end)
            if cut != -1:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = end - overlap
    return chunks


def load_pdf(path, source: str) -> list[dict]:
    """Chunk a PDF page by page so every chunk keeps its page number for citations."""
    records = []
    for page_num, page in enumerate(PdfReader(path).pages, start=1):
        for i, chunk in enumerate(chunk_text(page.extract_text() or "")):
            records.append({
                "id": f"{source}/{path.name}/p{page_num}/c{i}",
                "text": chunk,
                "metadata": {"source": source, "file": path.name, "page": page_num, "chunk_id": i},
            })
    return records


def get_collection(reset: bool = False):
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if reset and COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def ingest() -> dict[str, int]:
    collection = get_collection(reset=True)
    counts = {}
    for source in SOURCES:
        folder = DATA_DIR / source
        folder.mkdir(parents=True, exist_ok=True)
        records = []
        for pdf in sorted(folder.glob("*.pdf")):
            pdf_records = load_pdf(pdf, source)
            print(f"  {source:8} {pdf.name}: {len(pdf_records)} chunks")
            records.extend(pdf_records)
        # Chroma caps batch size, so add in slices.
        for i in range(0, len(records), 500):
            batch = records[i : i + 500]
            collection.add(
                ids=[r["id"] for r in batch],
                documents=[r["text"] for r in batch],
                metadatas=[r["metadata"] for r in batch],
            )
        counts[source] = len(records)
    return counts


if __name__ == "__main__":
    counts = ingest()
    print(f"Ingested {sum(counts.values())} chunks: {counts}")
    if not any(counts.values()):
        print(f"No PDFs found. Put files in {DATA_DIR / 'lecture'} and {DATA_DIR / 'textbook'}.")
