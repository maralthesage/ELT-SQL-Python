import csv
import pandas as pd
import psycopg2
from io import StringIO
import re

DB_CONFIG = "dbname=data_pipeline user=maralsheikhzadeh options='-c statement_timeout=900000'"
CSV_READ_ATTEMPTS = (
    ("utf-8", "c"),
    ("utf-8", "python"),
    ("latin1", "c"),
    ("latin1", "python"),
)

def clean_col(col):
    col = col.lower()
    col = re.sub(r'\W+', '_', col)
    return col.strip('_')

def read_csv_safe(path):
    last_error = None
    for encoding, engine in CSV_READ_ATTEMPTS:
        try:
            return pd.read_csv(path, sep=';', encoding=encoding, engine=engine, on_bad_lines='skip')
        except Exception as exc:
            last_error = exc
    raise last_error

def iter_csv_chunks_safe(path, chunksize):
    last_error = None

    for encoding, engine in CSV_READ_ATTEMPTS:
        try:
            reader = pd.read_csv(
                path,
                sep=';',
                encoding=encoding,
                engine=engine,
                on_bad_lines='skip',
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                chunksize=chunksize,
            )

            first_chunk = next(reader, None)
            if first_chunk is None:
                return iter(()), []

            cleaned_columns = [clean_col(col) for col in first_chunk.columns]
            first_chunk.columns = cleaned_columns

            def chunk_iterator():
                yield first_chunk
                for chunk in reader:
                    chunk.columns = cleaned_columns
                    yield chunk

            return chunk_iterator(), cleaned_columns
        except Exception as exc:
            last_error = exc

    raise last_error

def detect_csv_encoding(path, sample_size=65536):
    with open(path, "rb") as f:
        sample = f.read(sample_size)

    try:
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin1"

def read_csv_header_safe(path):
    last_error = None

    for encoding, _engine in CSV_READ_ATTEMPTS:
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f, delimiter=";")
                header = next(reader, None)
                if header is None:
                    return [], encoding
                return [clean_col(col) for col in header], encoding
        except Exception as exc:
            last_error = exc

    raise last_error

def get_connection():
    return psycopg2.connect(DB_CONFIG)

def quote_ident(name):
    return '"' + name.replace('"', '""') + '"'

def qualify_table(table, schema="staging"):
    if schema:
        return f"{quote_ident(schema)}.{quote_ident(table)}"
    return quote_ident(table)

def fetch_table_columns(cur, table, schema="staging"):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    return [row[0] for row in cur.fetchall()]

def ensure_text_table(cur, table, columns, schema="staging"):
    existing_columns = fetch_table_columns(cur, table, schema)
    if existing_columns:
        return False

    columns_sql = ", ".join(f"{quote_ident(col)} TEXT" for col in columns)
    cur.execute(
        f"CREATE TABLE {qualify_table(table, schema)} ({columns_sql});"
    )
    return True

def load_dataframe(cur, df, table, schema="staging"):
    buffer = StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    columns = ", ".join([quote_ident(col) for col in df.columns])

    copy_sql = f"""
    COPY {qualify_table(table, schema)} ({columns})
    FROM STDIN
    WITH (FORMAT csv)
    """

    cur.copy_expert(copy_sql, buffer)

def copy_csv_file(cur, path, table, columns, schema="staging", encoding=None):
    columns_sql = ", ".join([quote_ident(col) for col in columns])
    copy_sql = f"""
    COPY {qualify_table(table, schema)} ({columns_sql})
    FROM STDIN
    WITH (FORMAT csv, HEADER true, DELIMITER ';')
    """

    open_encoding = encoding or detect_csv_encoding(path)
    with open(path, "r", encoding=open_encoding, newline="") as f:
        cur.copy_expert(copy_sql, f)
