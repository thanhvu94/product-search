import os
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import logging

def setup_tracing(app: FastAPI, service_name: str):
    # Disabled as Jaeger not available in `Test` stage for Jenkins build
    if os.getenv("TESTING_MODE") == "true":
        logging.info("Tracing disabled for tests.")
        return
    
    # OTLPSpanExporter: send trace data to Jaeger (via OTEL_EXPORTER_OTLP_ENDPOINT)
    try:
        span_exporter = OTLPSpanExporter()
        logging.info("OTLP Span Exporter initialized.")
    except Exception as e:
        logging.error(f"Failed to initialize OTLP Span Exporter: {e}", exc_info=True)
        return

    # Define which service (via service_name) these traces are from
    resource = Resource(attributes={"service.name": service_name})
    
    # TracerProvider: global tracer manager
    provider = TracerProvider(resource=resource)
    # Collect and send spans in batch
    processor = BatchSpanProcessor(span_exporter) 
    provider.add_span_processor(processor)
    # Register as global tracer (all instrumentation will use ths provider)
    trace.set_tracer_provider(provider)
    
    # Automatically create traces for all incoming HTTP requests of FastAPI app instance
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
    logging.info("FastAPI instrumentation complete.")