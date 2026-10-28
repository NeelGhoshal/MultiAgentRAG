from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CHROMA_DIR = ROOT / "chroma_db"
PROGRESS_FILE = ROOT / "progress.json"

COLLECTION = "course"
SOURCES = ("lecture", "textbook")  # subfolder names under data/ == metadata tag

# Any OpenAI-compatible endpoint works; Groq hosts open-weight models with a free tier.
LLM_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "openai/gpt-oss-120b"  # open-weight (Apache 2.0); supports strict JSON-schema output on Groq

CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 150
TOP_K = 5
