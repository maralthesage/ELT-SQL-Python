import os
from ingest.utils import read_csv_safe, clean_col, get_connection, load_dataframe

def run_full_ingestion(base_path, file, table):
    path = os.path.join(base_path, file)

    conn = get_connection()
    cur = conn.cursor()

    df = read_csv_safe(path)
    print(f"    - read_csv returned {len(df)} rows for {file}", flush=True)
    df = df.astype(str)
    df.columns = [clean_col(col) for col in df.columns]

    columns_sql = [f'"{col}" TEXT' for col in df.columns]

    cur.execute(f"DROP TABLE IF EXISTS staging.{table};")
    cur.execute(f"""
        CREATE TABLE staging.{table} (
            {", ".join(columns_sql)}
        );
    """)
    conn.commit()

    print(f"    - loading {len(df)} rows into staging.{table} (COPY)", flush=True)
    try:
        load_dataframe(cur, df, table)
        conn.commit()
    except Exception:
        conn.rollback()
        # Keep staging table as TEXT for retry by dropping+recreating if needed
        print(f"    - load failed for staging.{table}; dropping table", flush=True)
        cur.execute(f"DROP TABLE IF EXISTS staging.{table};")
        conn.commit()
        cur.close()
        conn.close()
        raise

    cur.close()
    conn.close()

    print(f"FULL → {table} loaded", flush=True)
    return len(df)