"""Copy kaggle.json into ~/.kaggle/ so the Kaggle API can authenticate.

The credentials file is never copied into the repo (it is also gitignored).

Usage:
    python scripts/00_setup_kaggle_creds.py [path/to/kaggle.json]
Default search order: the given path, ./kaggle.json, ~/Downloads/kaggle.json
"""
import shutil
import sys
from pathlib import Path

from _common import ROOT

TARGET = Path.home() / ".kaggle" / "kaggle.json"


def main():
    if TARGET.exists():
        print(f"Kaggle credentials already in place: {TARGET}")
        return

    candidates = [Path(a) for a in sys.argv[1:]] + [
        ROOT / "kaggle.json",
        Path.home() / "Downloads" / "kaggle.json",
    ]
    source = next((c for c in candidates if c.is_file()), None)
    if source is None:
        raise SystemExit("kaggle.json not found. Pass its path as an argument.")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, TARGET)
    try:
        TARGET.chmod(0o600)  # Kaggle warns if the file is readable by others
    except OSError:
        pass
    print(f"Copied {source} -> {TARGET}")


if __name__ == "__main__":
    main()
