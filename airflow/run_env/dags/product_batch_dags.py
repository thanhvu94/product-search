import os
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# Path to task scripts
SCRIPT_DIR = "/opt/airflow/scripts"

def cleanup_data(**kwargs):
    # Clean up data
    import shutil
    import os
    
    DATA_DIR = "./staging_data/current_batch"
    data_dir = os.path.dirname(DATA_DIR)
    if os.path.exists(data_dir):
        print(f"Cleaning up data directory: {data_dir}")
        shutil.rmtree(data_dir)
        
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    'product_data_batch_pipeline',
    default_args=default_args,
    description='MinIO to Postgres batch ETL with GX validation.',
    schedule_interval='0 * * * *', # Runs hourly
    catchup=False,
    tags=['product', 'batch', 'spark'],
) as dag:
    
    # --- Task 1: Extract and Read Data with Spark ---
    t1_extract_read = BashOperator(
        task_id='extract_and_read',
        bash_command=f'python {os.path.join(SCRIPT_DIR, "extract_and_read.py")}',
        cwd=SCRIPT_DIR,
        env={**os.environ, "PYTHONPATH": SCRIPT_DIR}
    )

    # --- Task 2: Validate GX and Load to Postgres ---
    t2_validate_load = BashOperator(
        task_id='validate_and_load_to_postgres',
        bash_command=f'python {os.path.join(SCRIPT_DIR, "validate_and_write.py")}',
        cwd=SCRIPT_DIR,
        env={**os.environ, "PYTHONPATH": SCRIPT_DIR}
    )
    
    # --- Task 3: Cleanup ---
    t3_cleanup_data = PythonOperator(
        task_id='cleanup_data',
        python_callable=cleanup_data,
        trigger_rule='all_done', 
    )

    # Define the workflow sequence
    t1_extract_read >> t2_validate_load >> t3_cleanup_data