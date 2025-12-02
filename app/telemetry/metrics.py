from prometheus_fastapi_instrumentator import Instrumentator

def setup_metrics(app):
    # Create an `Instrumentator` instance for Prometheus monitoring metrics of a FastAPI app
    instrumentator = Instrumentator(
        # Exclude the metrics/health endpoints
        excluded_handlers=["/metrics", "/health"], 
    )
    
    ## Attach this instrumentator to FastAPI app
    # All HTTP requests will automatically update metrics
    instrumentator.instrument(app)
    
    ## Expose the /metrics endpoint
    # include_in_schema=False -> not appear in Swagger UI
    # should_gzip=True -> compress output to save bandwidth
    instrumentator.expose(app, include_in_schema=False, should_gzip=True)