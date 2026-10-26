import sys
import time
import uuid

from pipeline import config
from pipeline.ingest import ingest
from pipeline.logger import get_logger
from pipeline.metrics import publish
from pipeline.quality import run_checks
from pipeline.store import (close_db_connection, get_db_connection, write_csv,
                            write_parquet, write_table)
from pipeline.transform import aggregate, clean, enrich

log = get_logger("main")


def run():
    run_id = uuid.uuid4().hex[:8]
    start = time.time()
    metrics = {"run_id": run_id, "status": "failed"}
    log.info("Pipeline started", extra={"data": {"run_id": run_id, "source": config.SOURCE_PATH}})

    try:
        raw = ingest(config.SOURCE_PATH)
        metrics["rows_ingested"] = len(raw)

        clean_df, rejected = clean(raw)
        metrics["rows_clean"] = len(clean_df)
        metrics["rows_rejected"] = len(rejected)
        if len(rejected):
            write_csv(rejected, config.QUARANTINE_DIR, f"rejected_{run_id}.csv")

        metrics["quality"] = run_checks(len(raw), clean_df, rejected)

        enriched = enrich(clean_df, run_id)
        daily, wallets = aggregate(enriched)

        write_parquet(enriched, "transactions", partition_cols=["txn_month"])
        write_parquet(daily, "daily_summary.parquet")
        write_parquet(wallets, "wallet_features.parquet")

        conn, warehouse = get_db_connection()
        write_table(enriched, "fact_transactions", conn)
        write_table(daily, "agg_daily_summary", conn)
        write_table(wallets, "ml_wallet_features", conn)
        close_db_connection(conn)
        metrics["warehouse"] = warehouse

        metrics["fraud_txns"] = int(enriched["is_fraud"].sum())
        metrics["total_amount"] = round(float(enriched["amount"].sum()), 2)
        metrics["status"] = "success"
    except Exception as e:
        metrics["error"] = str(e)
        log.error("Pipeline failed", extra={"data": {"run_id": run_id, "error": str(e)}})
    finally:
        metrics["duration_seconds"] = round(time.time() - start, 2)
        publish(metrics)
        log.info("Pipeline finished", extra={"data": {
            "run_id": run_id, "status": metrics["status"],
            "duration_seconds": metrics["duration_seconds"]}})

    return 0 if metrics["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(run())
