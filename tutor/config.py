from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CHROMA_DIR = ROOT / "chroma_db"
PROGRESS_FILE = ROOT / "progress.json"

COLLECTION = "course"
SOURCES = ("lecture", "textbook")  # subfolder names under data/ == metadata tag

# Local model served by Ollama. qwen3:8b fits in 8 GB of VRAM; with 16+ GB, gpt-oss:20b is stronger.
MODEL = "qwen3:8b"
NUM_CTX = 8192  # context window; Ollama's default is too small for excerpts + answer + reasoning

# Hosted model on Groq's free tier, used instead of Ollama when GROQ_API_KEY is set (e.g. on Render).
# Override with the GROQ_MODEL env var.
GROQ_MODEL = "openai/gpt-oss-120b"

CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 150
TOP_K = 5
