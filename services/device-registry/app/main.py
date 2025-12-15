import time
from typing import List
from typing import Optional

import structlog
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Response
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import Histogram
from prometheus_client import generate_latest
from sqlalchemy.orm import Session

from .config import settings
from .database import engine
from .database import get_db
from .models import device as device_models
from .schemas import device as device_schemas
from .services.auth_service import AuthService
from .services.device_service import DeviceService

# Database tables
device_models.Base.metadata.create_all(bind=engine)

# Initialize logger
logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="Device Registry Service",
    description="IoT Device Registration and Management API",
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
    "device_registry_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "device_registry_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)

    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method, endpoint=request.url.path, status=response.status_code
    ).inc()

    REQUEST_DURATION.labels(method=request.method, endpoint=request.url.path).observe(
        time.time() - start_time
    )

    return response


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Dependency for authentication
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = await auth_service.verify_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "device-registry"}


@app.post("/devices", response_model=device_schemas.Device, tags=["Devices"])
async def create_device(
    device: device_schemas.DeviceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Register a new IoT device"""
    device_service = DeviceService(db)
    logger.info(
        "Creating device", device_id=device.device_id, user_id=current_user["sub"]
    )

    try:
        db_device = await device_service.create_device(device, current_user["sub"])
        return db_device
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/devices", response_model=List[device_schemas.Device], tags=["Devices"])
async def list_devices(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all devices for the authenticated user"""
    device_service = DeviceService(db)
    devices = await device_service.list_devices(
        user_id=current_user["sub"], skip=skip, limit=limit, status=status
    )
    return devices


@app.get("/devices/{device_id}", response_model=device_schemas.Device, tags=["Devices"])
async def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get device details by ID"""
    device_service = DeviceService(db)
    device = await device_service.get_device(device_id, current_user["sub"])
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@app.put("/devices/{device_id}", response_model=device_schemas.Device, tags=["Devices"])
async def update_device(
    device_id: str,
    device_update: device_schemas.DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update device information"""
    device_service = DeviceService(db)
    logger.info("Updating device", device_id=device_id, user_id=current_user["sub"])

    try:
        device = await device_service.update_device(
            device_id, device_update, current_user["sub"]
        )
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return device
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/devices/{device_id}", tags=["Devices"])
async def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a device"""
    device_service = DeviceService(db)
    logger.info("Deleting device", device_id=device_id, user_id=current_user["sub"])

    success = await device_service.delete_device(device_id, current_user["sub"])
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": "Device deleted successfully"}


@app.post(
    "/devices/{device_id}/authenticate",
    response_model=device_schemas.DeviceAuth,
    tags=["Devices"],
)
async def authenticate_device(
    device_id: str,
    auth_data: device_schemas.DeviceAuthRequest,
    db: Session = Depends(get_db),
):
    """Authenticate a device and return JWT token"""
    device_service = DeviceService(db)

    try:
        token = await device_service.authenticate_device(device_id, auth_data.api_key)
        return {"access_token": token, "token_type": "bearer"}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=settings.debug)
