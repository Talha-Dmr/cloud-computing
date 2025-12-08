from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class DataType(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    LIGHT = "light"
    MOTION = "motion"
    VOLTAGE = "voltage"
    CURRENT = "current"
    POWER = "power"
    GPS = "gps"
    CUSTOM = "custom"


class DataPoint(BaseModel):
    """Single data point from an IoT device"""

    metric_name: str = Field(..., description="Name of the metric")
    value: Union[float, int, str, bool] = Field(..., description="Value of the metric")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    data_type: DataType = Field(..., description="Type of data")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of measurement")
    quality: Optional[float] = Field(1.0, ge=0, le=1, description="Data quality score")
    metadata: Optional[Dict[str, Any]] = Field(
        default={}, description="Additional metadata"
    )

    @validator("timestamp", pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.utcnow()


class DataIngestionRequest(BaseModel):
    """Request to ingest data from an IoT device"""

    device_id: str = Field(
        ..., min_length=3, max_length=100, description="Device identifier"
    )
    data: List[DataPoint] = Field(
        ..., min_items=1, max_items=1000, description="List of data points"
    )
    batch_id: Optional[str] = Field(
        None, description="Batch identifier for grouping related data"
    )
    location: Optional[Dict[str, Any]] = Field(
        None, description="Device location information"
    )
    firmware_version: Optional[str] = Field(None, description="Device firmware version")
    battery_level: Optional[float] = Field(
        None, ge=0, le=100, description="Battery level percentage"
    )


class DataIngestionResponse(BaseModel):
    """Response for data ingestion request"""

    success: bool
    message: str
    processed_count: int
    batch_id: Optional[str] = None
    errors: Optional[List[str]] = None


class DeviceInfo(BaseModel):
    """Device information"""

    device_id: str
    device_type: str
    owner_id: str
    location: Optional[Dict[str, Any]]
    last_seen: datetime
    status: str


class HealthCheck(BaseModel):
    """Device health check report"""

    device_id: str
    is_healthy: bool
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metrics: Optional[Dict[str, Any]] = None


class DeviceStatus(BaseModel):
    """Device status information"""

    device_id: str
    status: str
    last_seen: datetime
    is_online: bool
    last_data_received: Optional[datetime]
    error_count: int = 0
    data_points_received: int = 0


class IngestionStats(BaseModel):
    """Service statistics"""

    total_devices: int
    active_devices: int
    data_points_today: int
    data_points_total: int
    messages_in_queue: int
    average_processing_time: float
    uptime: str


class AlertRule(BaseModel):
    """Alert rule definition"""

    id: str
    device_id: Optional[str]
    metric_name: str
    condition: str  # e.g., ">", "<", "==", "!="
    threshold: float
    severity: str  # "low", "medium", "high", "critical"
    is_active: bool = True
    created_at: datetime
    last_triggered: Optional[datetime]


class AlertEvent(BaseModel):
    """Alert event"""

    id: str
    rule_id: str
    device_id: str
    metric_name: str
    current_value: float
    threshold: float
    severity: str
    message: str
    triggered_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
