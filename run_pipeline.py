import sys
import time
import uuid
import signal
import traceback
import psycopg2

from config.tables import FILES
from ingest.ingest_full import run_full_ingestion
from ingest.ingest_incremental import run_incremental_ingestion

BASE_PATH = "/Volumes/MARAL/CSV/F01/"
DB_CONFIG = "dbname=data_pipeline user=maralsheikhzadeh options='-c statement_timeout=900000'"


def signal_handler(signum, frame):
    print("\n⛔ Received SIGINT/SIGTERM. Stopping pipeline gracefully...", flush=True)
    sys.exit(1)


def main():
    run_id = str(uuid.uuid4())
    print(f"🚀 Starting pipeline run_id={run_id}", flush=True)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Connecting to DB: {DB_CONFIG}", flush=True)
    conn = psycopg2.connect(DB_CONFIG)
    cur = conn.cursor()

    for file, meta in FILES.items():
        table = meta["table"]
        mode = meta["mode"]
        print(f"-- Processing file={file}, table=staging.{table}, mode={mode}", flush=True)

        start_time = time.time()

        try:
            # Avoid full-table COUNT(*) on large tables; this can block/hang.
            before_count = 0

            if mode == "full":
                rows_loaded = run_full_ingestion(BASE_PATH, file, table)
                rows_inserted = rows_loaded
            elif mode == "incremental":
                rows_loaded, rows_inserted = run_incremental_ingestion(
                    BASE_PATH,
                    file,
                    table,
                    meta,
                )
            else:
                raise ValueError(f"Unknown mode {mode} for table {table}")

            after_count = before_count + rows_inserted

            duration = round(time.time() - start_time, 2)

            cur.execute(
                """
                INSERT INTO analytics.pipeline_log (
                    run_id,
                    table_name,
                    load_type,
                    rows_in_file,
                    rows_loaded,
                    rows_inserted,
                    total_rows_after,
                    duration_seconds,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    table,
                    mode,
                    rows_loaded,
                    rows_loaded,
                    rows_inserted,
                    after_count,
                    duration,
                    "success",
                ),
            )
            conn.commit()
            print(
                f"✅ {table}: loaded={rows_loaded}, inserted={rows_inserted}, after={after_count}, duration={duration}s",
                flush=True,
            )

        except KeyboardInterrupt:
            print("\n⛔ KeyboardInterrupt received. Rolling back and exiting.", flush=True)
            conn.rollback()
            conn.close()
            sys.exit(1)

        except Exception as e:
            conn.rollback()
            print(f"❌ {table} failed: {e}", flush=True)
            traceback.print_exc()
            cur.execute(
                """
                INSERT INTO analytics.pipeline_log (
                    run_id,
                    table_name,
                    load_type,
                    status,
                    error_message
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (run_id, table, mode, "failed", str(e)),
            )
            conn.commit()
            raise

    print("-- Running transform.sql", flush=True)
    with open("sql/transform.sql", "r") as f:
        cur.execute(f.read())
        
    print("-- Running rechnung_model.sql", flush=True)
    with open("sql/rechnung_model.sql") as f:
        cur.execute(f.read())
        
    conn.commit()
    cur.close()
    conn.close()
    print("\n🎯 Pipeline complete.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ Pipeline interrupted by user.", flush=True)
        sys.exit(1)
    except Exception:
        print("\n💥 Pipeline crashed with exception:", flush=True)
        traceback.print_exc()
        sys.exit(1)
