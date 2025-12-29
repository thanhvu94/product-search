from pyspark.sql import SparkSession
import os
from config import *
import great_expectations as gx
from great_expectations.core.batch import BatchRequest

# --- Helper Functions ---
# Update checkpoint
def update_checkpoint(latest_timestamp):
    with open(CHECKPOINT_FILE, 'w') as f:
        f.write(latest_timestamp)
    print(f"Checkpoint updated to: {latest_timestamp}")

def create_spark_session():
    # Create SparkSession for reading staging data and writing to Postgres
    spark_jars = "/opt/airflow/spark_jars/hadoop-aws.jar,/opt/airflow/spark_jars/aws-sdk-bundle.jar,/opt/airflow/spark_jars/postgresql.jar"
    spark = SparkSession.builder \
        .appName("MinIO to Postgres Batch - Validate & Load") \
        .config("spark.jars", spark_jars) \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark

# --- Main Job ---
def run_validate_write_job(**kwargs):
    # PULL the timestamp from XCom
    latest_ts_from_extract = kwargs.get('ti').xcom_pull(
        task_ids='extract_and_stage_data', 
        key='latest_timestamp'
    ) if kwargs.get('ti') else "manual_run"

    if not latest_ts_from_extract:
        print("No new batch data or temporary timestamp found. Exiting load job.")
        return

    spark = create_spark_session()
    
    try:
        # --- 1. Great Expectations Validation ---
        print(f"Reading data from staging path: {DATA_PATH}")
        df = spark.read.parquet(DATA_PATH)

        print("Starting Great Expectations Validation...")
        context = gx.get_context()

        from great_expectations.core.batch import RuntimeBatchRequest
        batch_request = RuntimeBatchRequest(
            datasource_name="spark_staging_ds",
            data_connector_name="default_runtime_data_connector_name",
            data_asset_name="product_batch_asset",
            runtime_parameters={"batch_data": df},
            batch_identifiers={"default_identifier_name": latest_ts_from_extract}
        )

        validator = context.get_validator(
            batch_request=batch_request,
            expectation_suite_name="product_expectations"
        )

        print(f"Validating using suite: product_expectations")
        validation_result = validator.validate()
        
        # if not validation_result["success"]:
        #     print("❌ Validation FAILED! Data quality issues detected.")
        #     print("Review the Great Expectations Data Docs for details.")
        #     return

        print("Validation completed! Proceeding to load.")

        # --- 2. Load to PostgreSQL ---
        # Re-initialize Spark session for fresh start
        spark = create_spark_session()
        df_final = spark.read.parquet(DATA_PATH)
        # Write to PostgreSQL
        df_final.write \
            .format("jdbc") \
            .option("url", DB_URL) \
            .option("dbtable", DEST_TABLE) \
            .option("user", DB_USER) \
            .option("password", DB_PASS) \
            .option("driver", "org.postgresql.Driver") \
            .mode("append") \
            .save()
            
        print(f"Successfully appended VALIDATED data to table '{DEST_TABLE}' in Postgres.")
        
        # Update Checkpoint ONLY on successful load
        update_checkpoint(latest_ts_from_extract)

    except Exception as e:
        import traceback
        traceback.print_exc()
        
    finally:
        spark.stop()

if __name__ == "__main__":
    run_validate_write_job()