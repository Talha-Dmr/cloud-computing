import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from ..database import Base


class DeviceStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class DeviceType(PyEnum):
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    GATEWAY = "gateway"
    CONTROLLER = "controller"


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    device_type = Column(Enum(DeviceType), nullable=False)
    status = Column(Enum(DeviceStatus), default=DeviceStatus.INACTIVE)
    manufacturer = Column(String(200))
    model = Column(String(200))
    firmware_version = Column(String(50))
    api_key = Column(String(255), unique=True, nullable=False)

    # Metadata
    metadata_json = Column(Text)  # JSON string for additional metadata

    # Ownership
    owner_id = Column(String(100), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_seen = Column(DateTime(timezone=True))

    # Location
    latitude = Column(String(50))
    longitude = Column(String(50))
    location_name = Column(String(200))

    # Connectivity
    ip_address = Column(String(45))
    mac_address = Column(String(17))

    # Health
    is_healthy = Column(Boolean, default=True)
    health_check_interval = Column(String(20), default="300")  # seconds
    last_health_check = Column(DateTime(timezone=True))


class DeviceMetrics(Base):
    __tablename__ = "device_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(String(500), nullable=False)
    unit = Column(String(20))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    class Config:
        indexes = [
            ("device_id", "metric_name", "timestamp"),
        ]
