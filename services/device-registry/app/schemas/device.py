from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"

class DeviceType(str, Enum):
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    GATEWAY = "gateway"
    CONTROLLER = "controller"

class DeviceBase(BaseModel):
    device_id: str = Field(..., min_length=3, max_length=100, description="Unique device identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Device name")
    description: Optional[str] = Field(None, description="Device description")
    device_type: DeviceType = Field(..., description="Type of device")
    manufacturer: Optional[str] = Field(None, max_length=200, description="Device manufacturer")
    model: Optional[str] = Field(None, max_length=200, description="Device model")
    firmware_version: Optional[str] = Field(None, max_length=50, description="Firmware version")
    latitude: Optional[str] = Field(None, max_length=50, description="GPS latitude")
    longitude: Optional[str] = Field(None, max_length=50, description="GPS longitude")
    location_name: Optional[str] = Field(None, max_length=200, description="Human readable location")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")

class DeviceCreate(DeviceBase):
    api_key: Optional[str] = Field(None, description="API key (auto-generated if not provided)")

class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[DeviceStatus] = None
    manufacturer: Optional[str] = Field(None, max_length=200)
    model: Optional[str] = Field(None, max_length=200)
    firmware_version: Optional[str] = Field(None, max_length=50)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    location_name: Optional[str] = Field(None, max_length=200)
    metadata: Optional[Dict[str, Any]] = None
    health_check_interval: Optional[str] = Field(None, description="Health check interval in seconds")

class Device(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: DeviceStatus
    api_key: str  # In production, this should be masked
    owner_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    last_seen: Optional[datetime]
    ip_address: Optional[str]
    mac_address: Optional[str]
    is_healthy: bool
    health_check_interval: str
    last_health_check: Optional[datetime]

class DeviceList(BaseModel):
    devices: list[Device]
    total: int
    page: int
    per_page: int

class DeviceAuthRequest(BaseModel):
    api_key: str = Field(..., description="Device API key")

class DeviceAuth(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DeviceMetrics(BaseModel):
    device_id: str
    metrics: Dict[str, float]
    timestamp: datetime

class HealthCheck(BaseModel):
    device_id: str
    is_healthy: bool
    message: Optional[str] = None
    timestamp: datetime