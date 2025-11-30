from fastapi import FastAPI, UploadFile, File, Form
from app.api.search import perform_image_search, perform_text_search, perform_upsert_product
from app.telemetry.tracing import setup_tracing
from app.telemetry.metrics import setup_metrics
from app.logs.logging import setup_logging
import logging

setup_logging()

def create_app():
    # Init a FastAPI instance
    app = FastAPI(title="Product Search")

    # Init tracing & metrics
    setup_tracing(app, "product-search")
    setup_metrics(app)
    logging.info("Telemetry and metrics setup complete.")

    # Register upsert and search functions as POST APIs
    @app.post("/search_by_image")
    async def search_by_image(file: UploadFile = File(...), top_k: int = 5):
        img_bytes = await file.read()
        return perform_image_search(img_bytes, top_k)
    
    @app.post("/search_by_text")
    async def search_by_text(query: str = Form(...), top_k: int = 5):
        return perform_text_search(query, top_k)
    
    @app.post("/upsert_product")
    async def upsert_product(file: UploadFile = File(...), metadata_json: str = Form(...)):
        return await perform_upsert_product(file, metadata_json)

    logging.info("Application setup complete.")
    return app

app = create_app()