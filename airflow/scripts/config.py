# config.py

import os

# --- MinIO Configuration ---
MINIO_ENDPOINT = "http://minio:9000"
ACCESS_KEY = "minio_access_key"
SECRET_KEY = "minio_secret_key"
BUCKET_NAME = "product-data-lake"

# --- PostgreSQL Configuration ---
DB_URL = "jdbc:postgresql://offline-fs:5432/offline"
DB_USER = "offline"
DB_PASS = "offline"
DEST_TABLE = "offline_products"

# --- Checkpoint & Staging Configuration ---
# File to store the latest processed timestamp
CHECKPOINT_FILE = "spark_batch_checkpoint.txt" 
# Local path for the intermediate data batch
DATA_PATH = "./staging_data/current_batch" 

# File format used in the ETL script: products_batch_{start_idx}_{end_idx}_{YYYYMMDD_HHMMSS}.parquet
TIMESTAMP_PATTERN = r"(\d{8}_\d{6})"