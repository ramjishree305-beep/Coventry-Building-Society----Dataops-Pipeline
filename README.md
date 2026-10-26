# DataOps Pipeline – Financial Transactions (cloud-free)

A simple pipeline that **ingests**, **cleans**, **enriches**, **aggregates** and **stores**
financial (metaverse/crypto) transaction data for analytics and ML.
**No cloud account needed:** it runs on your laptop with Python and Docker, and CI runs on GitHub's free servers.

```
 data/raw/*.csv (local landing zone)
      │
      ▼
 INGEST ──▶ CLEAN ──▶ QUALITY GATE ──▶ ENRICH ──▶ AGGREGATE ──▶ STORE
              │            │                                     │
              ▼            ▼                                     ▼
     data/quarantine/   stop if > 5%              data/processed/*.parquet
     (bad rows + reason)  rows rejected           PostgreSQL in Docker (mock Redshift)
                                                  or data/warehouse.db (SQLite fallback)

 CI/CD: GitHub Actions     IaC: Docker Compose + Terraform (Docker provider)     Secrets: .env file
 Logs: logs/pipeline.log (JSON)     Run metrics: run_report.json + logs/run_history.csv
```

| Brief asks for | This repo uses | Cloud needed? |
|---|---|---|
| Ingest from S3 or local directory | Local folder `data/raw/` | No |
| Transform with Python | pandas (`pipeline/transform.py`) | No |
| Parquet or mock Redshift/PostgreSQL | Parquet files + PostgreSQL in Docker | No |
| CI/CD (e.g. GitHub Actions) | `.github/workflows/pipeline.yml` | No – GitHub's free runners |
| IaC (Terraform / Docker containers) | `docker-compose.yml`, `infra/main.tf` (Docker provider) | No |
| Monitoring / logging | JSON logs, run report, run history | No |
| Secrets (Vault or env variables) | Environment variables from a git-ignored `.env` | No |

## Project structure

```
pipeline/
  config.py        settings (each can be overridden with an environment variable)
  secret_store.py  reads secrets from environment variables, never from code
  logger.py        JSON logging to screen and logs/pipeline.log
  ingest.py        read every CSV/JSON in data/raw/
  transform.py     clean(), enrich(), aggregate()
  quality.py       data quality gate
  store.py         Parquet files + PostgreSQL (or SQLite when no DB_HOST is set)
  metrics.py       run report + run history
  main.py          runs all steps in order
tests/             15 unit tests (pytest)
Dockerfile         the pipeline image
docker-compose.yml Postgres + pipeline, one command
infra/main.tf      the same stack as Terraform (Docker provider)
.github/workflows/ CI: tests → terraform validate → build → run on Postgres → verify
.env.example       template for your local secret
data/raw/          input: 78,600 transactions
data/samples/      a deliberately "dirty" batch for the data-quality demo
presentation/      DataOps_Pipeline_Presentation.pptx (14 slides, speaker notes included)
```

## Prerequisites
- Python 3.11+
- Docker Desktop (for Postgres) – open it before the Docker commands
- Terraform 1.5+ (only for option 3)

## Option 1 – Python only (fastest, uses SQLite)
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -v                          # 15 unit tests
python -m pipeline.main            # writes Parquet + data/warehouse.db
```

## Option 2 – Docker Compose with PostgreSQL (recommended for the demo)
```bash
cp .env.example .env               # then edit DB_PASSWORD in .env
mkdir -p logs
docker compose up --build          # starts Postgres, runs the pipeline once, loads 3 tables
```
Query the warehouse:
```bash
docker compose exec postgres psql -U pipeline -d analytics \
  -c "select location_region, sum(fraud_count) from agg_daily_summary group by 1;"
```
Run the dirty batch: `SOURCE_PATH=data/samples docker compose run --rm pipeline` (exits with code 1).
Clean up: `docker compose down -v`.

## Option 3 – Terraform (Infrastructure as Code, Docker provider)
```bash
cd infra
export TF_VAR_db_password=change-me      # Windows PowerShell: $env:TF_VAR_db_password="change-me"
terraform init
terraform apply                          # network + Postgres + image + runs the pipeline
docker logs dataops-pipeline             # see the run
terraform destroy                        # remove everything
```
Use option 2 **or** option 3 at a time – both publish Postgres on port 5432.

## CI/CD – GitHub Actions
Push the repo to GitHub and the workflow runs on every push / pull request (or manually from the Actions tab):
1. **test** – `pytest`
2. **terraform** – `terraform fmt -check` and `terraform validate`
3. **run-pipeline** – builds the Docker image, runs the pipeline against a Postgres service,
   checks the warehouse row counts, runs the dirty batch and **expects it to fail**, uploads the logs

Any non-zero exit code fails the build. Optional: add a repository secret `DB_PASSWORD`
(Settings → Secrets and variables → Actions); without it CI uses a throwaway password for its temporary database.

## Secrets
- The only secret is the database password. It lives in `.env` (git-ignored); `.env.example` is the committed template.
- `secret_store.get_secret()` reads it from the environment and gives a clear error if it is missing. It is never logged.
- CI uses GitHub Secrets; Terraform uses `TF_VAR_db_password`, marked `sensitive`.
- In AWS the same environment variable would be injected by Secrets Manager or Vault – no code change.

## What you get

| Output | What it is |
|---|---|
| `fact_transactions` (Postgres/SQLite) + `data/processed/transactions/` (Parquet by month) | All cleaned + enriched rows |
| `agg_daily_summary` + `daily_summary.parquet` | Per day and region: count, total, fraud rate, risk |
| `ml_wallet_features` + `wallet_features.parquet` | One row per wallet: features for fraud models |
| `data/quarantine/rejected_<run>.csv` | Rows that failed a rule, with `reject_reason` |
| `data/processed/run_report.json` | Latest run: row counts, quality results, duration |
| `logs/pipeline.log`, `logs/run_history.csv` | JSON log of every step; one line per run |

## Data quality
Row rules (bad rows go to quarantine with a reason): missing values · amount ≤ 0 ·
risk_score outside 0–100 · unknown transaction type / anomaly label · invalid wallet
address (`0x` + 40 hex) · unparseable timestamp · duplicates removed.

Dataset gate (the run stops and nothing is loaded if any fail): reject rate ≤ 5% ·
no null/negative amounts · risk score in range · no duplicates · row counts reconcile.

## Live demo script
```bash
pytest -v                                               # 1. 15 tests pass
docker compose up --build                               # 2. Postgres + pipeline: 78,600 rows loaded
cat data/processed/run_report.json                      # 3. run metrics
SOURCE_PATH=data/samples docker compose run --rm pipeline   # 4. dirty batch: gate FAILS (22.7% > 5%)
cat data/quarantine/*.csv                               # 5. rejected rows with reasons
docker compose exec postgres psql -U pipeline -d analytics -c "select count(*) from fact_transactions;"   # 6. SQL
# 7. open the GitHub Actions tab and show the green run
```
