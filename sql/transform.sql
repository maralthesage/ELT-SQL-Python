-- =========================
-- CUSTOMER CLEANING
-- =========================

-- rename nummer → customer_id (only if exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='stamm_customers' AND column_name='nummer'
    ) THEN
        ALTER TABLE staging.stamm_customers RENAME COLUMN nummer TO customer_id;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='stat_customers' AND column_name='nummer'
    ) THEN
        ALTER TABLE staging.stat_customers RENAME COLUMN nummer TO customer_id;
    END IF;
END $$;

-- clean + zfill
UPDATE staging.stamm_customers
SET customer_id = LPAD(REGEXP_REPLACE(customer_id, '[^0-9]', '', 'g'), 10, '0')
WHERE customer_id IS NOT NULL;

UPDATE staging.stat_customers
SET customer_id = LPAD(REGEXP_REPLACE(customer_id, '[^0-9]', '', 'g'), 10, '0')
WHERE customer_id IS NOT NULL;


-- =========================
-- EXTRACT CUSTOMER FROM VERWEIS
-- =========================

ALTER TABLE staging.rechnungs_head
ADD COLUMN IF NOT EXISTS customer_id TEXT;

UPDATE staging.rechnungs_head
SET customer_id = LPAD(
    REGEXP_REPLACE(SUBSTRING(verweis FROM 2 FOR 11), '[^0-9]', '', 'g'),
    10,
    '0'
);


-- =========================
-- MARKETING PRODUCT KEYS
-- =========================

-- marketing_stamm: banummer → product_marketing_id
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='marketing_stamm' AND column_name='banummer'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='marketing_stamm' AND column_name='product_marketing_id'
    ) THEN
        ALTER TABLE staging.marketing_stamm RENAME COLUMN banummer TO product_marketing_id;
    END IF;
END $$;

-- other marketing tables: nummer → product_marketing_id
DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT table_name FROM information_schema.tables 
             WHERE table_schema='staging'
               AND table_name LIKE 'marketing_%'
               AND table_name <> 'marketing_stamm'
    LOOP
        EXECUTE format(
            'DO $inner$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name=''%s'' AND column_name=''nummer''
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name=''%s'' AND column_name=''product_marketing_id''
                ) THEN
                    ALTER TABLE staging.%s RENAME COLUMN nummer TO product_marketing_id;
                END IF;
            END $inner$;', t, t, t
        );
    END LOOP;
END $$;


-- =========================
-- LAGER PRODUCT KEYS
-- =========================

-- lager_stamm: lanummer → product_lager_id
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='lager_stamm' AND column_name='lanummer'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='lager_stamm' AND column_name='product_lager_id'
    ) THEN
        ALTER TABLE staging.lager_stamm RENAME COLUMN lanummer TO product_lager_id;
    END IF;
END $$;

-- other lager tables: nummer → product_lager_id
DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT table_name FROM information_schema.tables 
             WHERE table_schema='staging'
               AND table_name LIKE 'lager_%'
               AND table_name <> 'lager_stamm'
    LOOP
        EXECUTE format(
            'DO $inner$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name=''%s'' AND column_name=''nummer''
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name=''%s'' AND column_name=''product_lager_id''
                ) THEN
                    ALTER TABLE staging.%s RENAME COLUMN nummer TO product_lager_id;
                END IF;
            END $inner$;', t, t, t
        );
    END LOOP;
END $$;
