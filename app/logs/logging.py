import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    # Log at level INFO, WARNING, ERROR, CRITICAL
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Format raw logs into JSON format
    formatter = jsonlogger.JsonFormatter(
        # JSON: timestamp, log level, message
        '%(asctime)s %(levelname)s %(message)s'
    )
    # Format and send logs to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # For uvicorn and opentelemetry, only emit from level WARNING
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)