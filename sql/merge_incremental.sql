CREATE INDEX IF NOT EXISTS idx_rechnungs_head_rech_nr ON staging.rechnungs_head (rech_nr);
CREATE INDEX IF NOT EXISTS idx_rechnungs_details_key ON staging.rechnungs_details (rechnung, art_nr, groesse, farbe, preis);
CREATE INDEX IF NOT EXISTS idx_lager_historie_key ON staging.lager_historie (nummer, buchdatum, belegnr, bestmealt);

INSERT INTO staging.rechnungs_head (
    verweis,
    adr_lfd,
    auftrag_nr,
    batch_nr,
    herkunft,
    typ,
    datum,
    mediacode,
    abwicklung,
    rech_art,
    provision,
    best_wert,
    rech_nr,
    mwst1,
    mwst2,
    mwst3,
    sys_status,
    auf_anlage,
    ek_ges,
    sysvk_ges,
    sys_opid
)
SELECT
    t.verweis,
    t.adr_lfd,
    t.auftrag_nr,
    t.batch_nr,
    t.herkunft,
    CASE
        WHEN t.typ IS NULL OR btrim(t.typ) = '' OR lower(btrim(t.typ)) = 'nan' THEN NULL
        WHEN lower(btrim(t.typ)) IN ('true', 't', '1', 'yes', 'y') THEN TRUE
        WHEN lower(btrim(t.typ)) IN ('false', 'f', '0', 'no', 'n') THEN FALSE
        ELSE NULL
    END,
    t.datum,
    t.mediacode,
    CASE
        WHEN t.abwicklung IS NULL OR btrim(t.abwicklung) = '' OR lower(btrim(t.abwicklung)) = 'nan' THEN NULL
        WHEN lower(btrim(t.abwicklung)) IN ('true', 't', '1', 'yes', 'y') THEN TRUE
        WHEN lower(btrim(t.abwicklung)) IN ('false', 'f', '0', 'no', 'n') THEN FALSE
        ELSE NULL
    END,
    t.rech_art,
    t.provision,
    t.best_wert,
    t.rech_nr,
    t.mwst1,
    t.mwst2,
    t.mwst3,
    t.sys_status,
    t.auf_anlage,
    t.ek_ges,
    t.sysvk_ges,
    t.sys_opid
FROM staging.rechnungs_head_temp t
WHERE NOT EXISTS (
    SELECT 1
    FROM staging.rechnungs_head s
    WHERE s.rech_nr = t.rech_nr
);

INSERT INTO staging.rechnungs_details (
    rechnung,
    pos_nr,
    projekt,
    art_nr,
    groesse,
    farbe,
    menge,
    preis,
    mwst,
    mwst_kz,
    bezeichng,
    indi_kz,
    retouregrd,
    retoureart,
    ek,
    rabatt,
    sys_status
)
SELECT
    t.rechnung,
    t.pos_nr,
    t.projekt,
    t.art_nr,
    t.groesse,
    t.farbe,
    t.menge,
    t.preis,
    t.mwst,
    t.mwst_kz,
    t.bezeichng,
    t.indi_kz,
    t.retouregrd,
    t.retoureart,
    t.ek,
    t.rabatt,
    t.sys_status
FROM staging.rechnungs_details_temp t
WHERE NOT EXISTS (
    SELECT 1
    FROM staging.rechnungs_details s
    WHERE s.rechnung = t.rechnung
      AND s.art_nr = t.art_nr
      AND s.groesse = t.groesse
      AND s.farbe = t.farbe
      AND s.preis = t.preis
);

INSERT INTO staging.lager_historie (
    nummer,
    menge,
    ort,
    bereich,
    stellplatz,
    bezugkz,
    bezugnr,
    belegnr,
    buchdatum,
    buchkey,
    ek_preiskz,
    ek_preis,
    ek_zpreis,
    sys_art,
    sys_opid,
    sys_beweg,
    sys_anlage,
    druck,
    chargennr,
    nebenkost,
    nebenkost1,
    nebenkost2,
    nebenkost3,
    bestmealt,
    ek_alt,
    fw_kz,
    fw_kurs,
    ek_preisbl
)
SELECT
    t.nummer,
    t.menge,
    t.ort,
    t.bereich,
    t.stellplatz,
    t.bezugkz,
    t.bezugnr,
    t.belegnr,
    t.buchdatum,
    t.buchkey,
    t.ek_preiskz,
    t.ek_preis,
    t.ek_zpreis,
    t.sys_art,
    t.sys_opid,
    t.sys_beweg,
    t.sys_anlage,
    t.druck,
    t.chargennr,
    t.nebenkost,
    t.nebenkost1,
    t.nebenkost2,
    t.nebenkost3,
    t.bestmealt,
    t.ek_alt,
    t.fw_kz,
    t.fw_kurs,
    t.ek_preisbl
FROM staging.lager_historie_temp t
WHERE NOT EXISTS (
    SELECT 1
    FROM staging.lager_historie s
    WHERE s.nummer = t.nummer
      AND s.buchdatum = t.buchdatum
      AND s.belegnr = t.belegnr
      AND s.bestmealt = t.bestmealt
);

DROP TABLE IF EXISTS staging.rechnungs_head_temp;
DROP TABLE IF EXISTS staging.rechnungs_details_temp;
DROP TABLE IF EXISTS staging.lager_historie_temp;
