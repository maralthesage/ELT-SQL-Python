import hashlib
import os

from ingest.utils import (
    copy_csv_file,
    ensure_text_table,
    fetch_table_columns,
    get_connection,
    qualify_table,
    quote_ident,
    read_csv_header_safe,
)

TARGET_COLUMN_ALIASES = {
    "lager_historie": {
        "nummer": "product_lager_id",
    },
}

BOOLEAN_COLUMNS = {
    "rechnungs_head": {"typ", "abwicklung"},
}


def _parse_copy_rowcount(statusmessage):
    if not statusmessage:
        return None

    parts = statusmessage.split()
    if len(parts) == 2 and parts[0] == "COPY":
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def _boolean_expr(alias, column):
    ref = f"{alias}.{quote_ident(column)}"
    return f"""
    CASE
        WHEN {ref} IS NULL OR btrim({ref}) = '' OR lower(btrim({ref})) = 'nan' THEN NULL
        WHEN lower(btrim({ref})) IN ('true', 't', '1', 'yes', 'y') THEN TRUE
        WHEN lower(btrim({ref})) IN ('false', 'f', '0', 'no', 'n') THEN FALSE
        ELSE NULL
    END
    """.strip()


def _build_index_name(table, keys):
    digest = hashlib.md5(f"{table}:{','.join(keys)}".encode("utf-8")).hexdigest()[:10]
    return f"idx_{table[:32]}_{digest}"


def _resolved_target_column(table, source_column, target_columns):
    alias = TARGET_COLUMN_ALIASES.get(table, {}).get(source_column)
    if alias and alias in target_columns:
        return alias
    if source_column in target_columns:
        return source_column
    return None

def _ensure_target_index(cur, table, key_columns):
    index_name = _build_index_name(table, key_columns)
    index_cols_sql = ", ".join(quote_ident(col) for col in key_columns)
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_ident(index_name)} "
        f"ON {qualify_table(table)} ({index_cols_sql});"
    )


def _normalized_source_text_expr(alias, column, table):
    ref = f"{alias}.{quote_ident(column)}" if alias else quote_ident(column)
    if column in BOOLEAN_COLUMNS.get(table, set()):
        return f"""
        CASE
            WHEN {ref} IS NULL OR btrim({ref}) = '' OR lower(btrim({ref})) = 'nan' THEN ''
            WHEN lower(btrim({ref})) IN ('true', 't', '1', 'yes', 'y') THEN 'true'
            WHEN lower(btrim({ref})) IN ('false', 'f', '0', 'no', 'n') THEN 'false'
            ELSE lower(btrim({ref}))
        END
        """.strip()
    return f"COALESCE({ref}, '')"


def _normalized_target_text_expr(alias, target_column, source_column, table):
    ref = f"{alias}.{quote_ident(target_column)}" if alias else quote_ident(target_column)
    if source_column in BOOLEAN_COLUMNS.get(table, set()):
        return f"COALESCE(lower(btrim({ref}::text)), '')"
    return f"COALESCE({ref}, '')"


def _build_row_hash_expr(alias, table, source_columns, source_to_target, use_target_columns):
    exprs = []
    for source_column in source_columns:
        target_column = source_to_target.get(source_column)
        if not target_column:
            continue
        if use_target_columns:
            exprs.append(_normalized_target_text_expr(alias, target_column, source_column, table))
        else:
            exprs.append(_normalized_source_text_expr(alias, source_column, table))

    if not exprs:
        return "md5('')"

    joined_expr = f" || E'\\x1f' || ".join(exprs)
    return f"md5({joined_expr})"


def _ensure_hash_index(cur, table, source_columns, source_to_target):
    index_name = _build_index_name(table, ["__row_hash__"])
    hash_expr = _build_row_hash_expr(None, table, source_columns, source_to_target, use_target_columns=True)
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS {quote_ident(index_name)} "
        f"ON {qualify_table(table)} (({hash_expr}));"
    )


def _all_keys_present_and_unique(cur, table_name, key_columns, schema):
    qualified_table = qualify_table(table_name, schema)
    key_cols_sql = ", ".join(quote_ident(col) for col in key_columns)
    non_blank_sql = " AND ".join(
        f"NULLIF(btrim({quote_ident(col)}), '') IS NOT NULL" for col in key_columns
    )

    cur.execute(
        f"""
        SELECT NOT EXISTS (
            SELECT 1
            FROM {qualified_table}
            WHERE NOT ({non_blank_sql})
            LIMIT 1
        )
        AND NOT EXISTS (
            SELECT 1
            FROM (
                SELECT {key_cols_sql}
                FROM {qualified_table}
                WHERE {non_blank_sql}
                GROUP BY {key_cols_sql}
                HAVING COUNT(*) > 1
                LIMIT 1
            ) dup
        );
        """
    )
    return cur.fetchone()[0]


def _validate_key_meta(table, meta):
    key_candidates = meta.get("key_candidates")
    keys = meta.get("keys")

    if key_candidates is not None:
        if not isinstance(key_candidates, list) or not key_candidates:
            raise ValueError(f"Invalid key_candidates for {table}: expected a non-empty list")
        if not all(isinstance(candidate, list) and candidate for candidate in key_candidates):
            raise ValueError(
                f"Invalid key_candidates for {table}: expected a list of non-empty key lists, "
                f"for example [[\"rech_nr\"], [\"rech_nr\", \"datum\"]]"
            )
        if not all(all(isinstance(col, str) for col in candidate) for candidate in key_candidates):
            raise ValueError(f"Invalid key_candidates for {table}: all key names must be strings")
        return

    if keys is None:
        raise ValueError(f"Missing keys/key_candidates for {table}")
    if not isinstance(keys, list) or not keys or not all(isinstance(col, str) for col in keys):
        raise ValueError(
            f"Invalid keys for {table}: expected a non-empty list of column names, "
            f"for example [\"rech_nr\", \"datum\"]"
        )


def _resolve_keys(cur, table, temp_table, meta, target_columns):
    _validate_key_meta(table, meta)
    key_candidates = meta.get("key_candidates")
    if not key_candidates:
        return {"kind": "columns", "source_keys": meta["keys"]}

    for source_keys in key_candidates:
        target_keys = [
            _resolved_target_column(table, key, target_columns)
            for key in source_keys
        ]
        if any(col is None for col in target_keys):
            continue

        source_is_unique = _all_keys_present_and_unique(cur, temp_table, source_keys, schema=None)
        if not source_is_unique:
            continue

        target_is_unique = _all_keys_present_and_unique(cur, table, target_keys, schema="staging")
        if target_is_unique:
            return {"kind": "columns", "source_keys": source_keys}

    return {"kind": "row_hash"}


def _build_merge_sql(table, temp_table, source_columns, key_strategy, target_columns):
    source_to_target = {}
    for source_column in source_columns:
        target_column = _resolved_target_column(table, source_column, target_columns)
        if target_column:
            source_to_target[source_column] = target_column

    insert_target_columns = [source_to_target[col] for col in source_columns if col in source_to_target]
    insert_target_columns_sql = ", ".join(quote_ident(col) for col in insert_target_columns)
    dedup_columns_sql = ", ".join(quote_ident(col) for col in source_to_target)

    boolean_columns = BOOLEAN_COLUMNS.get(table, set())
    select_exprs = []
    for source_column in source_columns:
        if source_column not in source_to_target:
            continue
        if source_column in boolean_columns:
            select_exprs.append(_boolean_expr("d", source_column))
        else:
            select_exprs.append(f'd.{quote_ident(source_column)}')
    select_exprs_sql = ", ".join(select_exprs)

    if key_strategy["kind"] == "columns":
        source_keys = key_strategy["source_keys"]
        missing_keys = [key for key in source_keys if key not in source_to_target]
        if missing_keys:
            raise ValueError(
                f"Missing target columns for merge keys on {table}: {', '.join(missing_keys)}"
            )

        dedup_keys_sql = ", ".join(quote_ident(col) for col in source_keys)
        key_not_null_sql = " AND ".join(
            f"NULLIF(btrim({quote_ident(col)}), '') IS NOT NULL" for col in source_keys
        )
        exists_sql = " AND ".join(
            f"s.{quote_ident(source_to_target[key])} = d.{quote_ident(key)}" for key in source_keys
        )

        return f"""
WITH dedup AS (
    SELECT DISTINCT ON ({dedup_keys_sql}) {dedup_columns_sql}
    FROM {qualify_table(temp_table, schema=None)} t
    WHERE {key_not_null_sql}
    ORDER BY {dedup_keys_sql}
)
INSERT INTO {qualify_table(table)} ({insert_target_columns_sql})
SELECT {select_exprs_sql}
FROM dedup d
WHERE NOT EXISTS (
    SELECT 1
    FROM {qualify_table(table)} s
    WHERE {exists_sql}
);
"""

    source_row_hash_expr = _build_row_hash_expr(
        "t",
        table,
        source_columns,
        source_to_target,
        use_target_columns=False,
    )
    target_row_hash_expr = _build_row_hash_expr(
        "s",
        table,
        source_columns,
        source_to_target,
        use_target_columns=True,
    )

    return f"""
WITH dedup AS (
    SELECT DISTINCT ON (row_hash) {dedup_columns_sql}, row_hash
    FROM (
        SELECT {dedup_columns_sql}, {source_row_hash_expr} AS row_hash
        FROM {qualify_table(temp_table, schema=None)} t
    ) t
    WHERE row_hash IS NOT NULL
    ORDER BY row_hash
)
INSERT INTO {qualify_table(table)} ({insert_target_columns_sql})
SELECT {select_exprs_sql}
FROM dedup d
WHERE NOT EXISTS (
    SELECT 1
    FROM {qualify_table(table)} s
    WHERE {target_row_hash_expr} = d.row_hash
);
"""


def run_incremental_ingestion(base_path, file, table, meta):
    path = os.path.join(base_path, file)
    temp_table = f"{table}_temp"

    conn = get_connection()
    cur = conn.cursor()

    try:
        columns, file_encoding = read_csv_header_safe(path)
        if not columns:
            print(f"    - no rows found in {file}", flush=True)
            return 0, 0

        columns_sql = ", ".join(f"{quote_ident(col)} TEXT" for col in columns)
        cur.execute(f"CREATE TEMP TABLE {quote_ident(temp_table)} ({columns_sql}) ON COMMIT DROP;")
        cur.execute("SET LOCAL synchronous_commit = OFF;")

        copy_csv_file(cur, path, temp_table, columns, schema=None, encoding=file_encoding)
        rows_loaded = _parse_copy_rowcount(cur.statusmessage)
        if rows_loaded is None:
            cur.execute(f"SELECT COUNT(*) FROM {quote_ident(temp_table)};")
            rows_loaded = cur.fetchone()[0]
        print(f"    - staged {rows_loaded} rows into {temp_table}", flush=True)

        recreated_target = ensure_text_table(cur, table, columns)
        if recreated_target:
            print(
                f"    - staging.{table} was missing; recreated from {file} header",
                flush=True,
            )

        target_columns = fetch_table_columns(cur, table)
        if not target_columns:
            raise ValueError(f"Target table staging.{table} could not be created")

        key_strategy = _resolve_keys(cur, table, temp_table, meta, target_columns)
        if key_strategy["kind"] == "columns":
            keys = key_strategy["source_keys"]
            print(f"    - using incremental key for {table}: {keys}", flush=True)

            target_key_columns = [
                _resolved_target_column(table, key, target_columns)
                for key in keys
            ]
            if any(col is None for col in target_key_columns):
                missing = [key for key, col in zip(keys, target_key_columns) if col is None]
                raise ValueError(
                    f"Missing target key columns on staging.{table}: {', '.join(missing)}"
                )
            _ensure_target_index(cur, table, target_key_columns)
        else:
            print(f"    - no unique natural key found for {table}; using row fingerprint", flush=True)
            source_to_target = {
                source_column: _resolved_target_column(table, source_column, target_columns)
                for source_column in columns
                if _resolved_target_column(table, source_column, target_columns)
            }
            _ensure_hash_index(cur, table, columns, source_to_target)
        cur.execute(f"ANALYZE {quote_ident(temp_table)};")

        merge_sql = _build_merge_sql(table, temp_table, columns, key_strategy, target_columns)
        cur.execute(merge_sql)
        rows_inserted = cur.rowcount

        conn.commit()
        print(
            f"INCREMENTAL → {table}: staged={rows_loaded}, inserted={rows_inserted}",
            flush=True,
        )
        return rows_loaded, rows_inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
