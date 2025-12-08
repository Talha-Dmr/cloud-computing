import json
from typing import Any, Dict, List

import redis
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="IoT Data Ingestion Test", version="1.0.0")

# Test Redis connection
try:
    r = redis.Redis(host="localhost", port=6380, decode_responses=True)
    r.ping()
    REDIS_STATUS = "Connected"
except:
    REDIS_STATUS = "Failed to connect"


class DataPoint(BaseModel):
    metric_name: str
    value: float
    timestamp: str


class IngestData(BaseModel):
    device_id: str
    data: List[DataPoint]


@app.get("/")
async def root():
    return {"status": "IoT Data Ingestion Test", "redis": REDIS_STATUS}


@app.post("/ingest")
async def ingest_data(data: IngestData):
    # Store in Redis as a simple test
    key = f"device:{data.device_id}:latest"
    value = json.dumps([d.dict() for d in data.data])
    r.set(key, value, ex=3600)  # Expire in 1 hour

    return {
        "success": True,
        "device_id": data.device_id,
        "data_points": len(data.data),
        "stored": True,
    }


@app.get("/device/{device_id}")
async def get_device_data(device_id: str):
    key = f"device:{device_id}:latest"
    data = r.get(key)
    if data:
        return {"device_id": device_id, "data": json.loads(data)}
    return {"device_id": device_id, "data": None}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
