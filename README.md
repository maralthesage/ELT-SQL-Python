# ELT Pipeline (SQL + Python)

This project implements a simple ELT (Extract, Load, Transform) pipeline using Python and SQL.

Data is ingested and loaded using Python, while transformations are handled in SQL, following a typical data warehouse workflow.

## Overview

- Extract and load data with Python
- Transform data using SQL scripts
- Modular structure for ingestion, configuration, and transformations
- Designed as a minimal, reproducible ELT setup

## Structure

```

config/        # configuration
ingest/        # data ingestion scripts
sql/           # SQL transformations
run_pipeline.py
requirements.txt

````


## Usage

Run the pipeline:

```bash
python run_pipeline.py
```





