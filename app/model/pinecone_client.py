import os
import uuid
import io
from PIL import Image
import numpy as np
import torch
from transformers import CLIPProcessor, CLIPModel
from pinecone import Pinecone, ServerlessSpec


class PineConeManager:
    # Search on Pinecone with index "product-search" using cosine similarity
    def __init__(self,
                 index_name="product-search",
                 model=None,
                 processor=None,
                 device=None,
                 dimension=512,
                 metric="cosine"):
        # Must input clip_model and clip_processor
        if model is None or processor is None:
            raise ValueError("clip_model and clip_processor must be provided")
        
                # Get API key from environment
        api_key = os.environ.get("PINECONE_API_KEY")
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY not set in environment")
        self.pc = Pinecone(api_key=api_key)
        
        # Initialize and create index if not existed
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model
        self.processor = processor
        self.index_name = index_name
        existing = self.pc.list_indexes().names()
        if index_name not in existing:
            print(f"Creating index '{index_name}'...")
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                # Serverless: Pinecone fully manages storage / cloud compute
                # Only AWS supports free plan
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        self.index = self.pc.Index(index_name)

    def search(self, embedding, top_k=5, namespace="product-search"):
        # result: have vector ID, score, metadata
        result = self.index.query(vector=embedding.tolist(), 
                                  top_k=top_k,
                                  include_metadata=True, # return meta-data in result
                                  namespace=namespace)
        return result

    # Internal function used by `upsert_product_image` to generate image embedding
    def _generate_image_embedding(self, image_bytes: bytes) -> np.ndarray:
        # Convert raw image bytes into a processed PyTorch tensor
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self.processor(images=pil_image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            embedding = self.model.get_image_features(pixel_values=inputs["pixel_values"])

        embedding = embedding.cpu().numpy()[0]
        emb_normalized = embedding / np.linalg.norm(embedding) #L2 normalization for cosine search
        return emb_normalized

    def upsert_product_image(self, image_bytes: bytes, metadata: dict, namespace="product-search"):
        # Prepare data for upsert
        vector_id = metadata.get("id", str(uuid.uuid4())) # Vector ID = product ID
        embedding = self._generate_image_embedding(image_bytes) # Product image embedding
        vector_record = {
            "id": vector_id,
            "values": embedding.tolist(),
            "metadata": metadata,
        }

        # Upsert product
        self.index.upsert(
            vectors=[vector_record],
            namespace=namespace
        )

        return {
            "vector_id": vector_id,
            "status": "success",
            "namespace": namespace
        }