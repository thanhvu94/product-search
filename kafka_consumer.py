import json
from confluent_kafka import Consumer, KafkaException
from app.model.pinecone_client import PineConeManager
from app.api.schemas import ProductMetadata
from transformers import CLIPProcessor, CLIPModel
import torch
import os
import io
from streaming_data.utils.minio_client import MinioHandler

TOPIC = "products.public.products"
GROUP_ID = "product-cdc-consumer"

consumer = Consumer({
    "bootstrap.servers": "broker:29092",
    "group.id": GROUP_ID,
    "auto.offset.reset": "earliest"
})

consumer.subscribe([TOPIC])

# Set up HuggingFace CLIP model
clip_model_name = "openai/clip-vit-base-patch32"
device = "cuda" if torch.cuda.is_available() else "cpu"
clip_model = CLIPModel.from_pretrained(clip_model_name).to(device) # load weights (text+image encoders)
clip_processor = CLIPProcessor.from_pretrained(clip_model_name) # handle resizing, image normalization, text tokenization
pinecone = PineConeManager(index_name="product-search", dimension=512, model=clip_model, processor=clip_processor)

# MinIO handler to read product image from image bucket
minio_handler = MinioHandler()
BUCKET_IMAGES = "product-images"

def upsert_product(event):
    # Get product id & image name
    payload = event.get("payload", {})
    product_id = payload.get("id")
    image_filename = str(product_id) + ".jpg"
    
    try:
        response = minio_handler.client.get_object(BUCKET_IMAGES, image_filename)
        image_bytes = response.read()
        response.close()
        response.release_conn()
    except Exception as e:
        print(f"Error: Image {image_filename} not found in MinIO: {e}")
        return

    # Extract product data from Kafka message
    metadata_json = {}
    key_map = {
        "id": "id", "gender": "gender", "masterCategory": "mastercategory", 
        "subCategory": "subcategory", "articleType": "articletype", 
        "baseColour": "basecolour", "season": "season", "year": "year", 
        "usage": "usage", "productDisplayName": "productdisplayname"
    }
    for target_key, source_key in key_map.items():
        value = payload.get(source_key)
        
        # Handle None/Null values before sending to Pinecone
        if target_key == "year":
            # integer
            metadata_json[target_key] = int(value) if value not in (None, "") else 0
        else:
            # string
            is_null = value is None or str(value).strip().lower() in ("", "null", "none")
            if is_null:
                metadata_json[target_key] = ""
            else:
                metadata_json[target_key] = str(value)

    # Upsert data to Pinecone
    metadata = ProductMetadata(**metadata_json).dict()
    pinecone.upsert_product_image(
            image_bytes=image_bytes,
            metadata=metadata,
            namespace="product-search"
        )
    print("Upsert successfully", product_id)

print("Kafka consumer running...")

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue

    event = json.loads(msg.value().decode("utf-8"))
    upsert_product(event)

