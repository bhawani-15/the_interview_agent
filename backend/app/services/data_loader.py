import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_json(filename: str):
    file_path = DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_candidates():
    return load_json("candidates.json")


def load_curriculum():
    return load_json("curriculum.json")