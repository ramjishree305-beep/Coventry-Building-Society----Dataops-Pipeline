import glob
import os

import pandas as pd

from pipeline.logger import get_logger

log = get_logger("ingest")


def read_file(path):
    if path.endswith(".csv"):
        return pd.read_csv(path)
    if path.endswith(".json"):
        return pd.read_json(path, lines=True)
    raise ValueError(f"Unsupported file type: {path}")


def ingest(source_path):
    files = sorted(glob.glob(os.path.join(source_path, "*.csv")) +
                   glob.glob(os.path.join(source_path, "*.json")))

    if not files:
        raise FileNotFoundError(f"No CSV/JSON files found in {source_path}")

    frames = []
    for f in files:
        df = read_file(f)
        df["source_file"] = os.path.basename(f)
        frames.append(df)
        log.info("Read file", extra={"data": {"file": f, "rows": len(df)}})

    data = pd.concat(frames, ignore_index=True)
    log.info("Ingest complete", extra={"data": {"files": len(files), "rows": len(data)}})
    return data
