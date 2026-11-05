"""Add this folder to a repository WITHOUT overwriting any existing path."""
import argparse
import shutil
from pathlib import Path


def install(source, repo):
    repo = Path(repo).resolve()
    if not (repo / "backend/adafruit_mqtt.py").is_file() or not (repo / "firmware/src/main.cpp").is_file():
        raise ValueError("Choose YoloHome repository root (contains backend/ and firmware/)")
    target = repo / "tinyml-fire"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite {target}; compare the existing module first")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".venv*", ".pio", "__pycache__", ".env", "*.pyc"))
    return target


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True)
    a = p.parse_args()
    print(install(Path(__file__).resolve().parents[1], a.repo))
