import os
import sqlite3
import shutil

from pipeline import config
from pipeline.logger import get_logger
from pipeline.secret_store import get_secret

log = get_logger("store")


def write_parquet(df, name, partition_cols=None):
    path = os.path.join(config.OUTPUT_DIR, name)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # Replace the previous output so re-running the pipeline never appends
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)

    df.to_parquet(path, index=False, partition_cols=partition_cols)
    log.info("Wrote parquet", extra={"data": {"path": path, "rows": len(df)}})
    return path


def write_csv(df, folder, name):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    df.to_csv(path, index=False)
    return path


def get_db_connection():
    if config.DB_HOST:
        password = get_secret("DB_PASSWORD")

        from sqlalchemy import create_engine
        url = (f"postgresql+psycopg2://{config.DB_USER}:{password}"
               f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
        log.info("Using PostgreSQL warehouse", extra={"data": {"host": config.DB_HOST}})
        return create_engine(url), "postgres"

    os.makedirs(os.path.dirname(config.SQLITE_PATH) or ".", exist_ok=True)
    log.info("Using SQLite warehouse", extra={"data": {"path": config.SQLITE_PATH}})
    return sqlite3.connect(config.SQLITE_PATH), "sqlite"


def close_db_connection(conn):
    if hasattr(conn, "dispose"):
        conn.dispose()
    else:
        conn.close()


def write_table(df, table, conn):
    df.to_sql(table, conn, if_exists="replace", index=False, chunksize=10_000)
    log.info("Wrote table", extra={"data": {"table": table, "rows": len(df)}})
