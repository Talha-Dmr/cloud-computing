import asyncio
import json
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import structlog
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Response
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import Histogram
from prometheus_client import generate_latest

from .config import settings
from .schemas.ingestion import DataIngestionRequest
from .schemas.ingestion import DataIngestionResponse
from .schemas.ingestion import HealthCheck
from .services.ingestion_service import DataIngestionService
from .services.kafka_producer import KafkaProducerService
from .services.mqtt_service import MQTTService
from .services.redis_service import RedisService

# Initialize logger
logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Data Ingestion Service",
    description="IoT Data Ingestion and Processing API",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "data_ingestion_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "data_ingestion_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)

DATA_PROCESSED = Counter(
    "data_points_processed_total",
    "Total data points processed",
    ["source", "device_type"],
)

ACTIVE_DEVICES = Gauge("active_devices_count", "Number of currently active devices")

KAFKA_MESSAGES = Counter(
    "kafka_messages_produced_total",
    "Total Kafka messages produced",
    ["topic", "status"],
)

# Initialize services
kafka_producer = KafkaProducerService()
redis_service = RedisService()
mqtt_service = MQTTService()
ingestion_service = DataIngestionService(kafka_producer, redis_service)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)

    REQUEST_COUNT.labels(
        method=request.method, endpoint=request.url.path, status=response.status_code
    ).inc()

    REQUEST_DURATION.labels(method=request.method, endpoint=request.url.path).observe(
        time.time() - start_time
    )

    return response


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # Update active devices gauge
    active_count = await redis_service.get_active_devices_count()
    ACTIVE_DEVICES.set(active_count)

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Data Ingestion Service")

    # Initialize Kafka producer
    await kafka_producer.start()
    logger.info("Kafka producer started")

    # Initialize Redis connection
    await redis_service.connect()
    logger.info("Redis connected")

    # Start MQTT client in background
    asyncio.create_task(mqtt_service.start())
    logger.info("MQTT service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown"""
    logger.info("Shutting down Data Ingestion Service")

    await kafka_producer.stop()
    await redis_service.disconnect()
    await mqtt_service.stop()

    logger.info("All services stopped")


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "data-ingestion", "version": "1.0.0"}


@app.post("/ingest", response_model=DataIngestionResponse, tags=["Data Ingestion"])
async def ingest_data(
    data: DataIngestionRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Ingest IoT sensor data via HTTP

    This endpoint accepts sensor data from IoT devices, validates it,
    and forwards it to Kafka for processing.
    """
    logger.info(
        "Data ingestion request", device_id=data.device_id, data_points=len(data.data)
    )

    try:
        # Validate device authentication
        device_info = await ingestion_service.authenticate_device(
            credentials.credentials, data.device_id
        )

        if not device_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device credentials",
            )

        # Process the data asynchronously
        background_tasks.add_task(
            ingestion_service.process_data, data.dict(), device_info
        )

        # Update metrics
        DATA_PROCESSED.labels(
            source="http", device_type=device_info.get("device_type", "unknown")
        ).inc(len(data.data))

        return DataIngestionResponse(
            success=True,
            message=f"Successfully received {len(data.data)} data points",
            processed_count=len(data.data),
        )

    except Exception as e:
        logger.error("Data ingestion failed", error=str(e), device_id=data.device_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process data",
        )


@app.post(
    "/ingest/batch", response_model=DataIngestionResponse, tags=["Data Ingestion"]
)
async def ingest_batch_data(
    data_list: List[DataIngestionRequest],
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Ingest batch data from multiple devices or multiple readings
    """
    total_data_points = sum(len(data.data) for data in data_list)

    logger.info(
        "Batch data ingestion request",
        batch_size=len(data_list),
        total_data_points=total_data_points,
    )

    try:
        # For batch processing, we might want to validate all devices first
        # This is a simplified version - in production, you'd want more sophisticated batching
        for data in data_list:
            device_info = await ingestion_service.authenticate_device(
                credentials.credentials, data.device_id
            )

            if not device_info:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid credentials for device {data.device_id}",
                )

            background_tasks.add_task(
                ingestion_service.process_data, data.dict(), device_info
            )

        return DataIngestionResponse(
            success=True,
            message=f"Successfully queued {total_data_points} data points for processing",
            processed_count=total_data_points,
        )

    except Exception as e:
        logger.error("Batch data ingestion failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process batch data",
        )


@app.get("/device/{device_id}/status", tags=["Device Status"])
async def get_device_status(device_id: str):
    """Get real-time status of a device"""
    try:
        status = await redis_service.get_device_status(device_id)

        if not status:
            return {
                "device_id": device_id,
                "status": "unknown",
                "last_seen": None,
                "message": "Device not found or never connected",
            }

        return status

    except Exception as e:
        logger.error("Failed to get device status", device_id=device_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve device status",
        )


@app.get("/stats", tags=["Statistics"])
async def get_ingestion_stats():
    """Get ingestion service statistics"""
    try:
        stats = await ingestion_service.get_stats()
        return stats

    except Exception as e:
        logger.error("Failed to get stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics",
        )


@app.post("/health-check", tags=["Health"])
async def health_check(check: HealthCheck):
    """
    Health check endpoint for devices to report their status
    """
    try:
        await ingestion_service.update_device_health(
            check.device_id, check.is_healthy, check.message
        )

        return {
            "status": "received",
            "device_id": check.device_id,
            "timestamp": check.timestamp,
        }

    except Exception as e:
        logger.error("Health check failed", device_id=check.device_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process health check",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=settings.debug)
