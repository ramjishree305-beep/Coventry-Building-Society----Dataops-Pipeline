import pandas as pd

from pipeline.logger import get_logger

log = get_logger("transform")

REQUIRED_COLUMNS = [
    "timestamp", "sending_address", "receiving_address", "amount",
    "transaction_type", "location_region", "risk_score", "anomaly",
]
VALID_TYPES = {"purchase", "sale", "transfer", "scam", "phishing"}
VALID_ANOMALY = {"low_risk", "moderate_risk", "high_risk"}
ADDRESS_PATTERN = r"^0x[0-9a-f]{40}$"


def clean(df):
    df = df.copy()

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")

    for col in ["sending_address", "receiving_address", "transaction_type",
                "location_region", "anomaly", "purchase_pattern", "age_group"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    df["sending_address"] = df["sending_address"].str.lower()
    df["receiving_address"] = df["receiving_address"].str.lower()
    df["transaction_type"] = df["transaction_type"].str.lower()

    reason = pd.Series("", index=df.index)
    reason[df[REQUIRED_COLUMNS].isna().any(axis=1)] += "missing_value;"
    reason[df["amount"] <= 0] += "non_positive_amount;"
    reason[~df["risk_score"].between(0, 100)] += "risk_score_out_of_range;"
    reason[~df["transaction_type"].isin(VALID_TYPES)] += "unknown_transaction_type;"
    reason[~df["anomaly"].isin(VALID_ANOMALY)] += "unknown_anomaly_label;"
    reason[~df["sending_address"].str.match(ADDRESS_PATTERN, na=False)] += "bad_sender_address;"
    reason[~df["receiving_address"].str.match(ADDRESS_PATTERN, na=False)] += "bad_receiver_address;"

    rejected = df[reason != ""].assign(reject_reason=reason[reason != ""])
    good = df[reason == ""]

    before = len(good)
    good = good.drop_duplicates(subset=["timestamp", "sending_address", "receiving_address", "amount"])
    duplicates = before - len(good)

    log.info("Clean complete", extra={"data": {
        "rows_in": len(df), "rows_clean": len(good),
        "rows_rejected": len(rejected), "duplicates_removed": duplicates}})
    return good.reset_index(drop=True), rejected.reset_index(drop=True)


def enrich(df, run_id="manual"):
    df = df.copy()
    df["txn_date"] = df["timestamp"].dt.date.astype(str)
    df["txn_month"] = df["timestamp"].dt.strftime("%Y-%m")
    df["day_of_week"] = df["timestamp"].dt.day_name()
    df["is_weekend"] = df["timestamp"].dt.dayofweek >= 5
    df["is_night"] = df["timestamp"].dt.hour < 6
    df["is_fraud"] = df["transaction_type"].isin(["scam", "phishing"])
    df["is_self_transfer"] = df["sending_address"] == df["receiving_address"]
    df["amount_bucket"] = pd.cut(
        df["amount"], bins=[0, 100, 500, 1000, float("inf")],
        labels=["small", "medium", "large", "very_large"]).astype(str)
    df["risk_level"] = df["anomaly"].map({"low_risk": 0, "moderate_risk": 1, "high_risk": 2})
    df["pipeline_run_id"] = run_id
    df["processed_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    log.info("Enrich complete", extra={"data": {"columns": len(df.columns)}})
    return df


def aggregate(df):
    daily = (df.groupby(["txn_date", "location_region"])
               .agg(txn_count=("amount", "size"),
                    total_amount=("amount", "sum"),
                    avg_amount=("amount", "mean"),
                    fraud_count=("is_fraud", "sum"),
                    high_risk_count=("risk_level", lambda s: (s == 2).sum()),
                    avg_risk_score=("risk_score", "mean"))
               .reset_index())
    daily["fraud_rate"] = daily["fraud_count"] / daily["txn_count"]

    wallets = (df.groupby("sending_address")
                 .agg(txn_count=("amount", "size"),
                      total_sent=("amount", "sum"),
                      avg_amount=("amount", "mean"),
                      max_amount=("amount", "max"),
                      unique_receivers=("receiving_address", "nunique"),
                      avg_risk_score=("risk_score", "mean"),
                      fraud_ratio=("is_fraud", "mean"),
                      night_ratio=("is_night", "mean"),
                      first_seen=("timestamp", "min"),
                      last_seen=("timestamp", "max"))
                 .reset_index())

    log.info("Aggregate complete", extra={"data": {
        "daily_rows": len(daily), "wallet_rows": len(wallets)}})
    num_cols = wallets.select_dtypes("number").columns
    wallets[num_cols] = wallets[num_cols].round(4)
    return daily.round(4), wallets
