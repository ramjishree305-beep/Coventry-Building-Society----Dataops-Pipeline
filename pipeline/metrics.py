import csv
import json
import os

from pipeline import config


def publish(metrics):
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(config.OUTPUT_DIR, "run_report.json"), "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    history = os.path.join(config.LOG_DIR, "run_history.csv")
    os.makedirs(config.LOG_DIR, exist_ok=True)
    fields = ["run_id", "status", "rows_ingested", "rows_clean", "rows_rejected", "duration_seconds"]
    is_new = not os.path.exists(history)
    with open(history, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(metrics)
