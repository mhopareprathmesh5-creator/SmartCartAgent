"""Download the BigBasket product dataset from Kaggle into data/raw/.

Skips the download if the CSV is already there.
"""
from _common import KAGGLE_DATASET, RAW_CSV, RAW_DIR


def main():
    if RAW_CSV.exists():
        print(f"Dataset already present: {RAW_CSV}")
        return

    from kaggle.api.kaggle_api_extended import KaggleApi  # imported late: it authenticates on import

    api = KaggleApi()
    api.authenticate()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {KAGGLE_DATASET} ...")
    api.dataset_download_files(KAGGLE_DATASET, path=str(RAW_DIR), unzip=True)

    if not RAW_CSV.exists():
        raise SystemExit(f"Download finished but {RAW_CSV.name} not found in {RAW_DIR}")
    print(f"Saved to {RAW_CSV}")


if __name__ == "__main__":
    main()
