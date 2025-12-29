from pyspark.sql import SparkSession
from minio import Minio
from datetime import datetime
import re
import os
from config import *

def get_last_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return f.read().strip()
    # Return random checkpoint if no file found
    return "20000101_000000"

def save_latest_timestamp(latest_timestamp):
    with open(TEMP_TS_FILE, 'w') as f:
        f.write(latest_timestamp)
    print(f"Latest timestamp saved to temporary file: {latest_timestamp}")

# Get unread parquet files
def filter_new_parquet_files(last_timestamp_str):
    minio_client = Minio("minio:9000", access_key=ACCESS_KEY, secret_key=SECRET_KEY, secure=False)
    
    last_checkpoint = datetime.strptime(last_timestamp_str, "%Y%m%d_%H%M%S")
    new_files_paths = []
    latest_timestamp = last_timestamp_str

    try:
        objects = minio_client.list_objects(BUCKET_NAME, recursive=True)
        
        for obj in objects:
            file_name = obj.object_name
            if not file_name.endswith('.parquet'):
                continue
                
            match = re.search(TIMESTAMP_PATTERN, file_name)
            if match:
                file_timestamp_str = match.group(1)
                file_timestamp = datetime.strptime(file_timestamp_str, "%Y%m%d_%H%M%S")
                
                if file_timestamp > last_checkpoint:
                    s3a_path = f"s3a://{BUCKET_NAME}/{file_name}"
                    new_files_paths.append(s3a_path)
                    
                    if file_timestamp_str > latest_timestamp:
                        latest_timestamp = file_timestamp_str

    except Exception as e:
        print(f"MinIO/Filtering Error: {e}")
        return [], last_timestamp_str 

    new_files_paths.sort() 
    print(f"Found {len(new_files_paths)} new files since {last_timestamp_str}.")
    return new_files_paths, latest_timestamp

def create_spark_session():
    # Creates SparkSession
    spark_jars = "/opt/airflow/spark_jars/hadoop-aws.jar,/opt/airflow/spark_jars/aws-sdk-bundle.jar,/opt/airflow/spark_jars/postgresql.jar"
    
    spark = SparkSession.builder \
        .appName("MinIO to Postgres Batch") \
        .config("spark.jars", spark_jars) \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark

def run_extract_job(**kwargs):
    # Get new parquet files
    last_checkpoint_ts = get_last_checkpoint()
    new_files_paths, latest_ts = filter_new_parquet_files(last_checkpoint_ts)
    if not new_files_paths:
        print("No new files found. Exiting extract job.")
        kwargs['ti'].xcom_push(key='latest_timestamp', value=None)
        return

    spark = create_spark_session()
    
    try:
        # 1. Read new Parquet files
        print(f"Processing {len(new_files_paths)} files...")
        df = spark.read.parquet(*new_files_paths)
        
        # 2. Write to temporary Data Path
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        df.write.mode("overwrite").parquet(DATA_PATH)            
        print(f"Successfully wrote data: {DATA_PATH}")
        
        kwargs['ti'].xcom_push(key='latest_timestamp', value=latest_ts)
        print(f"Pushed latest timestamp to XCom: {latest_ts}")

    except Exception as e:
        print(f"Extract job failed: {e}")
        # kwargs['ti'].xcom_push(key='latest_timestamp', value=None)
        
    finally:
        spark.stop()

if __name__ == "__main__":
    run_extract_job()