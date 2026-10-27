from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CHROMA_DIR = ROOT / "chroma_db"
PROGRESS_FILE = ROOT / "progress.json"

COLLECTION = "course"
SOURCES = ("lecture", "textbook")  # subfolder names under data/ == metadata tag

MODEL = "claude-opus-5-5"

CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 150
TOP_K = 5
