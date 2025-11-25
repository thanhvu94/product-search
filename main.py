from fastapi import FastAPI, UploadFile, File, Form
from app.api.search import search_by_image, search_by_text, upsert_product
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
    async def _search_by_image(file: UploadFile = File(...), top_k: int = 5):
        img_bytes = await file.read()
        return await search_by_image(img_bytes, top_k)
    
    @app.post("/search_by_text")
    async def _search_by_text(query: str = Form(...), top_k: int = 5):
        return await search_by_text(query, top_k)
    
    @app.post("/upsert_product")
    async def _upsert_product(file: UploadFile = File(...), metadata_json: str = Form(...)):
        return await upsert_product(file, metadata_json)

    logging.info("Application setup complete.")
    return app

app = create_app()