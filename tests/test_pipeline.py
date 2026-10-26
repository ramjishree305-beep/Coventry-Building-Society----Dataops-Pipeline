import pandas as pd
import pytest

from pipeline.quality import DataQualityError, run_checks
from pipeline.transform import aggregate, clean, enrich

GOOD_ADDR_A = "0x" + "a" * 40
GOOD_ADDR_B = "0x" + "b" * 40


def make_row(**overrides):
    row = {
        "timestamp": "2022-04-11 12:47:27",
        "hour_of_day": 12,
        "sending_address": GOOD_ADDR_A,
        "receiving_address": GOOD_ADDR_B,
        "amount": 100.0,
        "transaction_type": "transfer",
        "location_region": "Europe",
        "ip_prefix": 192.0,
        "login_frequency": 3,
        "session_duration": 48,
        "purchase_pattern": "focused",
        "age_group": "established",
        "risk_score": 18.75,
        "anomaly": "low_risk",
    }
    row.update(overrides)
    return row


def test_clean_keeps_valid_rows():
    df = pd.DataFrame([make_row()])
    good, bad = clean(df)
    assert len(good) == 1
    assert len(bad) == 0


@pytest.mark.parametrize("bad_field, expected_reason", [
    ({"amount": -5}, "non_positive_amount"),
    ({"amount": None}, "missing_value"),
    ({"risk_score": 150}, "risk_score_out_of_range"),
    ({"transaction_type": "refund"}, "unknown_transaction_type"),
    ({"sending_address": "not-a-wallet"}, "bad_sender_address"),
    ({"timestamp": "not-a-date"}, "missing_value"),
])
def test_clean_rejects_bad_rows(bad_field, expected_reason):
    df = pd.DataFrame([make_row(**bad_field)])
    good, bad = clean(df)
    assert len(good) == 0
    assert expected_reason in bad.loc[0, "reject_reason"]


def test_clean_normalises_text():
    df = pd.DataFrame([make_row(transaction_type="  TRANSFER ",
                                sending_address=GOOD_ADDR_A.upper().replace("0X", "0x"))])
    good, _ = clean(df)
    assert good.loc[0, "transaction_type"] == "transfer"
    assert good.loc[0, "sending_address"] == GOOD_ADDR_A


def test_clean_removes_duplicates():
    df = pd.DataFrame([make_row(), make_row()])
    good, _ = clean(df)
    assert len(good) == 1


def test_enrich_adds_flags():
    df = pd.DataFrame([make_row(transaction_type="scam", timestamp="2022-04-09 03:00:00",
                                anomaly="high_risk")])
    good, _ = clean(df)
    out = enrich(good, run_id="test")
    row = out.iloc[0]
    assert bool(row["is_fraud"]) is True
    assert bool(row["is_weekend"]) is True
    assert bool(row["is_night"]) is True
    assert row["risk_level"] == 2
    assert row["amount_bucket"] == "small"
    assert row["pipeline_run_id"] == "test"


def test_aggregate_totals_match():
    rows = [make_row(amount=100, timestamp="2022-01-01 10:00:00"),
            make_row(amount=300, timestamp="2022-01-01 11:00:00", transaction_type="phishing")]
    good, _ = clean(pd.DataFrame(rows))
    daily, wallets = aggregate(enrich(good))
    assert daily["total_amount"].sum() == 400
    assert daily["fraud_count"].sum() == 1
    assert wallets.loc[0, "txn_count"] == 2
    assert wallets.loc[0, "fraud_ratio"] == 0.5


def test_quality_gate_passes_on_good_data():
    good, bad = clean(pd.DataFrame([make_row()]))
    assert run_checks(1, good, bad)["passed"]


def test_quality_gate_fails_when_too_many_rejects():
    rows = [make_row(amount=-1)] * 9 + [make_row()]
    good, bad = clean(pd.DataFrame(rows))
    with pytest.raises(DataQualityError):
        run_checks(len(rows), good, bad)


def test_secret_read_from_environment(monkeypatch):
    from pipeline.secret_store import get_secret
    monkeypatch.setenv("DB_PASSWORD", "from-env")
    assert get_secret("DB_PASSWORD") == "from-env"


def test_missing_secret_gives_clear_error(monkeypatch):
    from pipeline.secret_store import MissingSecretError, get_secret
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(MissingSecretError):
        get_secret("DB_PASSWORD")
