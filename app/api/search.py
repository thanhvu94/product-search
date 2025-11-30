from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.api.schemas import ProductMetadata
from PIL import Image
import io
import torch
from transformers import CLIPProcessor, CLIPModel
import numpy as np
import json
from app.model.pinecone_client import PineConeManager

# Create API router starting with /search, grouped together with tag "Search"
router = APIRouter(prefix="/search", tags=["Search"])

# Set up HuggingFace CLIP model
clip_model_name = "openai/clip-vit-base-patch32"
device = "cuda" if torch.cuda.is_available() else "cpu" 
clip_model = CLIPModel.from_pretrained(clip_model_name).to(device) # load weights (text+image encoders)
clip_processor = CLIPProcessor.from_pretrained(clip_model_name) # handle resizing, image normalization, text tokenization

# Init Pinecone helper
# dimension: 512 (28x28) matching embeddiing size
# index_name: place where vectors are stored
pinecone = PineConeManager(index_name="product-search", dimension=512, model=clip_model, processor=clip_processor)


### API search product by image
# Function to convert raw image bytes into embedding vectors
def get_image_embedding(image_bytes: bytes) -> np.ndarray:
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB") # get PIL images + RGB format (ready for CLIP model)
    inputs = clip_processor(images=pil_image, return_tensors="pt").to(device) # pre-process + return PyTorch tensor (pt)
    with torch.no_grad():
        # get image embeddings from tensor value
        embedding = clip_model.get_image_features(pixel_values=inputs["pixel_values"])
    # L2 normalization for cosine-similarity image search
    emb_normalized = embedding / embedding.norm(p=2, dim=-1, keepdim=True)
    return emb_normalized.cpu().numpy()[0]

@router.post("/image")
def perform_image_search(image: bytes, top_k: int = 5):
    embedding = get_image_embedding(image)
    results = pinecone.search(embedding, top_k=top_k, namespace="product-search")
    matches_dict = [match.to_dict() for match in results['matches']]
    return {"results": matches_dict}


### API search product by text
def get_text_embedding(text: str) -> np.ndarray:
    inputs = clip_processor(text=[text], return_tensors="pt").to(device)
    with torch.no_grad():
        # `inputs` is a dictionary
        # **inputs: get value of input_ids (tokenized text) and attention_mask (real token or padding)
        embedding = clip_model.get_text_features(**inputs)
    emb_normalized = embedding / embedding.norm(p=2, dim=-1, keepdim=True)
    return emb_normalized.cpu().numpy()[0]

@router.post("/text")
def perform_text_search(query: str = Form(...), top_k: int = 5):
    embedding = get_text_embedding(query)
    results = pinecone.search(embedding, top_k=top_k, namespace="product-search")
    matches_dict = [match.to_dict() for match in results['matches']]
    return {"results": matches_dict}


### API upsert a new product to vector database
@router.post("/upsert-product")
async def perform_upsert_product(image: UploadFile = File(...), metadata_json: str = Form(...)):
    # json.loads: convert metadata JSON string into dict
    metadata_dict = json.loads(metadata_json)
    # Ensure matching of structure & data type of base model (ProductMetadata)
    metadata = ProductMetadata(**metadata_dict).dict()

    # Read file into image bytes, then upload image+metadata to Pinecone in the specific namespace
    image_bytes = await image.read()
    result = pinecone.upsert_product_image(
        image_bytes=image_bytes,
        metadata=metadata,
        namespace="product-search"
    )

    return JSONResponse(
        content={"message": "Upsert successful",
                 "result": result},
        status_code=200
    )