from pipeline import config
from pipeline.logger import get_logger

log = get_logger("quality")


class DataQualityError(Exception):
    pass


def run_checks(raw_count, clean_df, rejected_df):
    reject_pct = 100 * len(rejected_df) / max(raw_count, 1)

    checks = {
        "has_rows": len(clean_df) > 0,
        "reject_rate_ok": reject_pct <= config.MAX_REJECT_PERCENT,
        "no_null_amounts": bool(clean_df["amount"].notna().all()),
        "amounts_positive": bool((clean_df["amount"] > 0).all()),
        "risk_score_in_range": bool(clean_df["risk_score"].between(0, 100).all()),
        "no_duplicate_txns": not clean_df.duplicated(
            subset=["timestamp", "sending_address", "receiving_address", "amount"]).any(),
        "row_count_reconciles": len(clean_df) <= raw_count,
    }

    results = {
        "checks": checks,
        "reject_percent": round(reject_pct, 2),
        "passed": all(checks.values()),
    }
    log.info("Quality checks finished", extra={"data": results})

    if not results["passed"]:
        failed = [name for name, ok in checks.items() if not ok]
        raise DataQualityError(f"Data quality checks failed: {failed}")
    return results
