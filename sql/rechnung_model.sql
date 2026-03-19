CREATE OR REPLACE TABLE analytics.rechnung_final AS

WITH rechnungs_head_clean AS (
    SELECT
        *,
        TO_CHAR(TO_DATE(auf_anlage, 'YYYY-MM-DD'), 'YYYY-MM-DD') AS auf_anlage_clean,
        TO_CHAR(TO_DATE(datum, 'YYYY-MM-DD'), 'YYYY-MM-DD') AS datum_clean,

        LPAD(REGEXP_REPLACE(rech_nr, '\.0$', ''), 12, '0') AS rech_nr_clean,

        LPAD(
            REGEXP_REPLACE(SUBSTRING(verweis FROM 2 FOR 10), '[^0-9]', '', 'g'),
            10,
            '0'
        ) AS customer_id

    FROM staging.rechnungs_head
    WHERE auf_anlage >= '2023-01-01'
),

rechnungs_details_clean AS (
    SELECT
        *,
        LPAD(REGEXP_REPLACE(rechnung, '\.0$', ''), 12, '0') AS rechnung_clean,

        CASE 
            WHEN preis ~ '^-?[0-9.]+$' AND preis::numeric < 0 THEN menge::numeric * -1
            ELSE menge::numeric
        END AS menge_clean

    FROM staging.rechnungs_details
),

product_groups AS (
    SELECT
        TRIM(product_marketing_id) AS art_nr,
        REGEXP_REPLACE(warengr, '\.0$', '') AS wg
    FROM staging.marketing_stamm
),

merged AS (
    SELECT
        h.*,
        d.art_nr,
        d.groesse,
        d.farbe,
        d.menge_clean AS menge,
        d.preis,
        d.mwst,
        d.rechnung_clean

    FROM rechnungs_head_clean h
    INNER JOIN rechnungs_details_clean d
        ON h.rech_nr_clean = d.rechnung_clean
),

enriched AS (
    SELECT
        m.*,
        pg.wg
    FROM merged m
    LEFT JOIN product_groups pg
        ON TRIM(m.art_nr) = pg.art_nr
),

final AS (
    SELECT DISTINCT
        verweis,

        LPAD(REGEXP_REPLACE(auftrag_nr, '\.0$', ''), 9, '0') AS auftrag_nr,

        herkunft,
        typ,
        datum_clean AS datum,
        mediacode,
        customer_id,
        auf_anlage_clean AS auf_anlage,
        rechnung_clean AS rechnung,
        projekt,
        art_nr,
        groesse,
        farbe,
        menge,
        preis,
        mwst,
        wg,
        ek,
        bezeichng,
        retouregrd,
        retoureart,
        rech_art,
        rabatt
    FROM enriched
)

SELECT * FROM final;