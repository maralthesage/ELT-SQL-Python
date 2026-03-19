FILES = {
    # ---------- FULL REFRESH ----------
    "V2AD1001.csv": {"table": "stamm_customers", "mode": "full"},
    "V2AD1005.csv": {"table": "stat_customers", "mode": "full"},
    "V2LA1001.csv": {"table": "lager_stamm", "mode": "full"},
    "V2LA1002.csv": {"table": "lager_bezeichnung", "mode": "full"},
    "V2LA1003.csv": {"table": "lager_lieferant", "mode": "full"},
    "V4LA1009.csv": {"table": "lager_zusatz", "mode": "full"},
    "V2AR1001.csv": {"table": "marketing_stamm", "mode": "full"},
    "V2AR1002.csv": {"table": "marketing_bezeichnung", "mode": "full"},
    "V2AR1005.csv": {"table": "marketing_sets", "mode": "full"},
    "V2AR1004.csv": {"table": "marketing_vk_preis", "mode": "full"},
    "V4AR1009.csv": {"table": "marketing_zusatz", "mode": "full"},


    # # # ---------- INCREMENTAL (APPEND ONLY) ----------
    "V2AD1056.csv": {
        "table": "rechnungs_head",
        "mode": "incremental",
        "keys": ["rech_nr", "datum"],
    },
    "V2AD1156.csv": {
        "table": "rechnungs_details",
        "mode": "incremental",
        "keys": ["rechnung", "art_nr", "groesse", "farbe", "preis"],
    },
    "V2LA1006.csv": {
        "table": "lager_historie",
        "mode": "incremental",
        "keys": ["nummer", "buchdatum", "belegnr", "bestmealt"],
    },
}
