import time
import schedule
import pandas as pd
import os
import torch
import logging
import numpy as np
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from utils.postgresql_client import PostgresSQLClient
from utils.minio_client import MinioHandler
from datetime import datetime

# --- Logging format ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configurations ---
CSV_FILE_PATH = "style.csv"  # Read product data
IMAGES_DIR = "./raw_images"   # Product raw images
BATCH_SIZE = 5              # Send 5 items every run
CHECKPOINT_FILE = "etl_checkpoint.txt" # Keep track of processed rows

# --- Initialize Models ---
device = "cuda" if torch.cuda.is_available() else "cpu"
model_name = "openai/clip-vit-base-patch32"
logging.info(f"Loading CLIP model: {model_name} on {device}...")
model = CLIPModel.from_pretrained(model_name).to(device)
processor = CLIPProcessor.from_pretrained(model_name)

# --- Get checkpoint helper functions ---
def get_last_processed_index():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return int(f.read().strip())
    return 0

def update_checkpoint(index):
    with open(CHECKPOINT_FILE, 'w') as f:
        f.write(str(index))

# --- Generate embeddings ---
def generate_embeddings(text, image_path):
    # Image embeddings
    try:
        image = Image.open(image_path).convert("RGB")
        img_inputs = processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            img_emb = model.get_image_features(**img_inputs)
            # L2 Normalize
            img_emb = img_emb / img_emb.norm(p=2, dim=-1, keepdim=True)
            img_emb_list = img_emb.cpu().numpy()[0].tolist()
    except Exception as e:
        logging.warning(f"Could not process image {image_path}: {e}")
        img_emb_list = None

    # Text embeddings
    try:
        txt_inputs = processor(text=[text], return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            txt_emb = model.get_text_features(**txt_inputs)
            # L2 Normalize
            txt_emb = txt_emb / txt_emb.norm(p=2, dim=-1, keepdim=True)
            txt_emb_list = txt_emb.cpu().numpy()[0].tolist()
    except Exception as e:
        logging.warning(f"Could not process text '{text}': {e}")
        txt_emb_list = None
        
    return img_emb_list, txt_emb_list

# --- Send data to PostgresDB (for Kafka streaming) ---
def upsert_to_postgres(df_batch):
    pg_client = PostgresSQLClient(
        database="k6",
        user="k6",
        password="k6",
    )
    upsert_query = """
    INSERT INTO products (
        id, gender, masterCategory, subCategory, articleType, 
        baseColour, season, year, usage, productDisplayName, 
        image_embedding, text_embedding, image_url, updated_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (id) DO UPDATE SET
        productDisplayName = EXCLUDED.productDisplayName,
        image_embedding = EXCLUDED.image_embedding,
        text_embedding = EXCLUDED.text_embedding,
        image_url = EXCLUDED.image_url,
        updated_at = NOW();
    """
    
    with pg_client.create_conn() as conn:
        with conn.cursor() as cur:
            for _, row in df_batch.iterrows():
                cur.execute(upsert_query, (
                    str(row['id']), row['gender'], row['masterCategory'], row['subCategory'],
                    row['articleType'], row['baseColour'], row['season'], int(row['year']) if pd.notna(row['year']) else 0,
                    row['usage'], row['productDisplayName'],
                    row['image_embedding'], row['text_embedding'],
                    row['image_url']
                ))
        conn.commit()
    logging.info(f"Upserted {len(df_batch)} rows to PostgreSQL.")

# --- Fake streaming job ---
def job():
    logging.info("Starting scheduled job...")
    minio_handler = MinioHandler()
    
    # Load data
    try:
        df = pd.read_csv(CSV_FILE_PATH, on_bad_lines='skip')
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        return

    # Check if we have data to process
    start_idx = get_last_processed_index()
    end_idx = start_idx + BATCH_SIZE
    if start_idx >= len(df):
        logging.info("All data processed")
        return   
    current_batch = df.iloc[start_idx:end_idx].copy()
    logging.info(f"Processing batch from index {start_idx} to {end_idx}")

    # Enrich data (generate embeddings)
    image_embeddings = []
    text_embeddings = []
    image_urls = []

    for _, row in current_batch.iterrows():
        prod_id = str(row['id'])
        img_filename = f"{prod_id}.jpg"
        img_path = os.path.join(IMAGES_DIR, img_filename)
        
        # Generate embeddings
        text_input = f"{row['productDisplayName']} {row['masterCategory']} {row['subCategory']}"
        img_emb, txt_emb = generate_embeddings(text_input, img_path)

        # Upload to MinIO
        img_url = minio_handler.upload_file(img_path, img_filename)
        if not img_url:
             img_url = ""

        image_embeddings.append(img_emb)
        text_embeddings.append(txt_emb)
        image_urls.append(img_url)

    current_batch['image_embedding'] = image_embeddings
    current_batch['text_embedding'] = text_embeddings
    current_batch['image_url'] = image_urls

    # Send data to MinIO
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parquet_filename = f"enriched_products_{start_idx}_{end_idx}_{timestamp}.parquet"
    minio_handler.upload_parquet(current_batch, parquet_filename)

    # Send to Postgres DB
    upsert_to_postgres(current_batch)

    # Update checkpoint
    update_checkpoint(end_idx)
    logging.info("Job finished.\n")

# --- Scheduler ---
if __name__ == "__main__":
    # Ensure tables exist
    import utils.create_table as create_table
    create_table.create_tables()

    # Run every 60 sec
    schedule.every(60).seconds.do(job)
    job()

    logging.info("Scheduler started. Waiting for next run...")
    while True:
        schedule.run_pending()
        time.sleep(1)