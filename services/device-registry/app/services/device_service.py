import json
import secrets
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import structlog
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..config import settings
from ..models import device as device_models
from ..schemas import device as device_schemas

logger = structlog.get_logger()


class DeviceService:
    def __init__(self, db: Session):
        self.db = db

    async def create_device(
        self, device_data: device_schemas.DeviceCreate, owner_id: str
    ) -> device_models.Device:
        """Create a new device"""
        # Check if device_id already exists
        existing = (
            self.db.query(device_models.Device)
            .filter(device_models.Device.device_id == device_data.device_id)
            .first()
        )

        if existing:
            raise ValueError(f"Device with ID {device_data.device_id} already exists")

        # Generate API key if not provided
        api_key = device_data.api_key or self._generate_api_key()

        # Convert metadata dict to JSON string
        metadata_json = (
            json.dumps(device_data.metadata) if device_data.metadata else "{}"
        )

        db_device = device_models.Device(
            device_id=device_data.device_id,
            name=device_data.name,
            description=device_data.description,
            device_type=device_data.device_type,
            manufacturer=device_data.manufacturer,
            model=device_data.model,
            firmware_version=device_data.firmware_version,
            api_key=api_key,
            owner_id=owner_id,
            metadata_json=metadata_json,
            latitude=device_data.latitude,
            longitude=device_data.longitude,
            location_name=device_data.location_name,
        )

        self.db.add(db_device)
        self.db.commit()
        self.db.refresh(db_device)

        logger.info(
            "Device created successfully",
            device_id=db_device.device_id,
            device_name=db_device.name,
            owner_id=owner_id,
        )

        return db_device

    async def list_devices(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[device_models.Device]:
        """List devices for a user with optional filtering"""
        query = self.db.query(device_models.Device).filter(
            device_models.Device.owner_id == user_id
        )

        if status:
            query = query.filter(device_models.Device.status == status)

        return query.offset(skip).limit(limit).all()

    async def get_device(
        self, device_id: str, owner_id: str
    ) -> Optional[device_models.Device]:
        """Get device by ID and owner"""
        return (
            self.db.query(device_models.Device)
            .filter(
                and_(
                    device_models.Device.device_id == device_id,
                    device_models.Device.owner_id == owner_id,
                )
            )
            .first()
        )

    async def update_device(
        self, device_id: str, device_update: device_schemas.DeviceUpdate, owner_id: str
    ) -> Optional[device_models.Device]:
        """Update device information"""
        db_device = await self.get_device(device_id, owner_id)
        if not db_device:
            return None

        # Update fields
        update_data = device_update.model_dump(exclude_unset=True)

        # Handle metadata separately
        if "metadata" in update_data:
            metadata_json = json.dumps(update_data["metadata"])
            update_data["metadata_json"] = metadata_json
            del update_data["metadata"]

        for field, value in update_data.items():
            setattr(db_device, field, value)

        db_device.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(db_device)

        logger.info(
            "Device updated successfully", device_id=device_id, owner_id=owner_id
        )

        return db_device

    async def delete_device(self, device_id: str, owner_id: str) -> bool:
        """Delete a device"""
        db_device = await self.get_device(device_id, owner_id)
        if not db_device:
            return False

        self.db.delete(db_device)
        self.db.commit()

        logger.info(
            "Device deleted successfully", device_id=device_id, owner_id=owner_id
        )

        return True

    async def authenticate_device(self, device_id: str, api_key: str) -> str:
        """Authenticate device and return JWT token"""
        device = (
            self.db.query(device_models.Device)
            .filter(
                and_(
                    device_models.Device.device_id == device_id,
                    device_models.Device.api_key == api_key,
                    device_models.Device.status == device_models.DeviceStatus.ACTIVE,
                )
            )
            .first()
        )

        if not device:
            raise ValueError("Invalid device credentials or device not active")

        # Update last seen
        device.last_seen = datetime.utcnow()
        self.db.commit()

        # Generate JWT token
        from .auth_service import AuthService

        auth_service = AuthService(self.db)
        token = auth_service.create_device_token(device_id)

        logger.info(
            "Device authenticated successfully",
            device_id=device_id,
            owner_id=device.owner_id,
        )

        return token

    async def update_device_status(
        self, device_id: str, status: device_models.DeviceStatus
    ) -> bool:
        """Update device status"""
        device = (
            self.db.query(device_models.Device)
            .filter(device_models.Device.device_id == device_id)
            .first()
        )

        if not device:
            return False

        device.status = status
        device.updated_at = datetime.utcnow()

        if status == device_models.DeviceStatus.ACTIVE:
            device.last_seen = datetime.utcnow()

        self.db.commit()

        logger.info(
            "Device status updated", device_id=device_id, new_status=status.value
        )

        return True

    async def update_health(
        self, device_id: str, is_healthy: bool, message: Optional[str] = None
    ) -> bool:
        """Update device health status"""
        device = (
            self.db.query(device_models.Device)
            .filter(device_models.Device.device_id == device_id)
            .first()
        )

        if not device:
            return False

        device.is_healthy = is_healthy
        device.last_health_check = datetime.utcnow()
        device.last_seen = datetime.utcnow()

        self.db.commit()

        logger.info(
            "Device health updated",
            device_id=device_id,
            is_healthy=is_healthy,
            message=message,
        )

        return True

    async def get_device_metrics(
        self, device_id: str, limit: int = 100
    ) -> List[device_models.DeviceMetrics]:
        """Get recent metrics for a device"""
        return (
            self.db.query(device_models.DeviceMetrics)
            .filter(device_models.DeviceMetrics.device_id == device_id)
            .order_by(device_models.DeviceMetrics.timestamp.desc())
            .limit(limit)
            .all()
        )

    def _generate_api_key(self) -> str:
        """Generate a secure API key"""
        return f"{settings.api_key_prefix}{secrets.token_urlsafe(32)}"
