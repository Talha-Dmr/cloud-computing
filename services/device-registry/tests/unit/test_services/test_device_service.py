"""
Unit Tests for Device Service Business Logic
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.models.device import Device, DeviceMetrics, DeviceStatus, DeviceType
from app.services.device_service import DeviceService


class TestDeviceService:
    """Test Device Service business logic"""

    @pytest.fixture
    def device_service(self, test_db_session):
        """Create device service instance"""
        return DeviceService(test_db_session)

    @pytest.fixture
    def sample_device(self, test_db_session, sample_device_data):
        """Create sample device in database"""
        device = Device(
            device_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            device_type=DeviceType.SENSOR,
            manufacturer=sample_device_data["manufacturer"],
            model=sample_device_data["model"],
            firmware_version=sample_device_data["firmware_version"],
            location=sample_device_data["location"],
            metadata=sample_device_data["metadata"],
            status=DeviceStatus.ACTIVE,
        )
        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)
        return device

    @pytest.mark.asyncio
    async def test_create_device_success(self, device_service, sample_device_data):
        """Test successful device creation"""
        device = await device_service.create_device(
            device_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            device_type=sample_device_data["device_type"],
            manufacturer=sample_device_data["manufacturer"],
            model=sample_device_data["model"],
            firmware_version=sample_device_data["firmware_version"],
            location=sample_device_data["location"],
            metadata=sample_device_data["metadata"],
        )

        assert device.device_id == sample_device_data["device_id"]
        assert device.name == sample_device_data["name"]
        assert device.device_type == DeviceType.SENSOR
        assert device.status == DeviceStatus.OFFLINE  # Default for new devices
        assert device.created_at is not None
        assert device.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_device_duplicate_id(
        self, device_service, sample_device, sample_device_data
    ):
        """Test creating device with duplicate ID raises exception"""
        with pytest.raises(ValueError, match="Device with ID .* already exists"):
            await device_service.create_device(
                device_id=sample_device_data["device_id"],  # Same ID
                name="Another Device",
                device_type=DeviceType.ACTUATOR,
            )

    @pytest.mark.asyncio
    async def test_get_device_by_id_success(self, device_service, sample_device):
        """Test getting device by ID"""
        found_device = await device_service.get_device_by_id(sample_device.device_id)

        assert found_device is not None
        assert found_device.device_id == sample_device.device_id
        assert found_device.name == sample_device.name
        assert found_device.device_type == sample_device.device_type

    @pytest.mark.asyncio
    async def test_get_device_by_id_not_found(self, device_service):
        """Test getting non-existent device returns None"""
        device = await device_service.get_device_by_id("non-existent-device")
        assert device is None

    @pytest.mark.asyncio
    async def test_list_devices_empty(self, device_service):
        """Test listing devices when none exist"""
        devices = await device_service.list_devices()
        assert devices == []

    @pytest.mark.asyncio
    async def test_list_devices_with_data(self, device_service, sample_device):
        """Test listing devices when some exist"""
        devices = await device_service.list_devices()
        assert len(devices) == 1
        assert devices[0].device_id == sample_device.device_id

    @pytest.mark.asyncio
    async def test_list_devices_with_pagination(self, device_service):
        """Test device listing with pagination"""
        # Create multiple devices
        for i in range(5):
            await device_service.create_device(
                device_id=f"device-{i:03d}",
                name=f"Device {i}",
                device_type=DeviceType.SENSOR,
            )

        # Test pagination
        page1 = await device_service.list_devices(skip=0, limit=2)
        page2 = await device_service.list_devices(skip=2, limit=2)
        page3 = await device_service.list_devices(skip=4, limit=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

        # Check that device IDs are in order
        all_devices = page1 + page2 + page3
        device_ids = [d.device_id for d in all_devices]
        assert device_ids == [
            "device-000",
            "device-001",
            "device-002",
            "device-003",
            "device-004",
        ]

    @pytest.mark.asyncio
    async def test_list_devices_by_status(self, device_service):
        """Test filtering devices by status"""
        # Create devices with different statuses
        await device_service.create_device(
            "active-device", "Active Device", DeviceType.SENSOR
        )
        await device_service.create_device(
            "offline-device", "Offline Device", DeviceType.SENSOR
        )

        # Update one device to ACTIVE status
        await device_service.update_device_status("active-device", DeviceStatus.ACTIVE)

        active_devices = await device_service.list_devices(status=DeviceStatus.ACTIVE)
        offline_devices = await device_service.list_devices(status=DeviceStatus.OFFLINE)

        assert len(active_devices) == 1
        assert len(offline_devices) == 1
        assert active_devices[0].device_id == "active-device"
        assert offline_devices[0].device_id == "offline-device"

    @pytest.mark.asyncio
    async def test_list_devices_by_type(self, device_service):
        """Test filtering devices by type"""
        # Create devices with different types
        await device_service.create_device(
            "sensor-device", "Sensor Device", DeviceType.SENSOR
        )
        await device_service.create_device(
            "actuator-device", "Actuator Device", DeviceType.ACTUATOR
        )

        sensor_devices = await device_service.list_devices(
            device_type=DeviceType.SENSOR
        )
        actuator_devices = await device_service.list_devices(
            device_type=DeviceType.ACTUATOR
        )

        assert len(sensor_devices) == 1
        assert len(actuator_devices) == 1
        assert sensor_devices[0].device_id == "sensor-device"
        assert actuator_devices[0].device_id == "actuator-device"

    @pytest.mark.asyncio
    async def test_update_device_success(self, device_service, sample_device):
        """Test successful device update"""
        updated_device = await device_service.update_device(
            sample_device.device_id,
            name="Updated Device Name",
            manufacturer="Updated Corp",
            firmware_version="2.0.0",
        )

        assert updated_device.name == "Updated Device Name"
        assert updated_device.manufacturer == "Updated Corp"
        assert updated_device.firmware_version == "2.0.0"
        assert updated_device.updated_at > sample_device.updated_at

    @pytest.mark.asyncio
    async def test_update_device_not_found(self, device_service):
        """Test updating non-existent device raises exception"""
        with pytest.raises(ValueError, match="Device with ID .* not found"):
            await device_service.update_device(
                "non-existent-device", name="Updated Name"
            )

    @pytest.mark.asyncio
    async def test_update_device_status(self, device_service, sample_device):
        """Test updating device status"""
        original_status = sample_device.status
        new_status = DeviceStatus.MAINTENANCE

        updated_device = await device_service.update_device_status(
            sample_device.device_id, new_status
        )

        assert updated_device.status == new_status
        assert updated_device.updated_at > sample_device.updated_at

    @pytest.mark.asyncio
    async def test_delete_device_success(self, device_service, sample_device):
        """Test successful device deletion"""
        result = await device_service.delete_device(sample_device.device_id)

        assert result is True

        # Verify device is deleted
        deleted_device = await device_service.get_device_by_id(sample_device.device_id)
        assert deleted_device is None

    @pytest.mark.asyncio
    async def test_delete_device_not_found(self, device_service):
        """Test deleting non-existent device returns False"""
        result = await device_service.delete_device("non-existent-device")
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_device_success(self, device_service, sample_device):
        """Test successful device authentication"""
        # Mock device secret/key validation
        with patch.object(
            device_service, "_validate_device_credentials"
        ) as mock_validate:
            mock_validate.return_value = True

            result = await device_service.authenticate_device(
                sample_device.device_id, "valid-secret-or-token"
            )

            assert result is True
            mock_validate.assert_called_once_with(
                sample_device.device_id, "valid-secret-or-token"
            )

    @pytest.mark.asyncio
    async def test_authenticate_device_not_found(self, device_service):
        """Test authenticating non-existent device returns False"""
        result = await device_service.authenticate_device(
            "non-existent-device", "any-secret"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_device_invalid_credentials(
        self, device_service, sample_device
    ):
        """Test authenticating device with invalid credentials returns False"""
        with patch.object(
            device_service, "_validate_device_credentials"
        ) as mock_validate:
            mock_validate.return_value = False

            result = await device_service.authenticate_device(
                sample_device.device_id, "invalid-secret-or-token"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_get_device_statistics(self, device_service):
        """Test getting device statistics"""
        # Create devices with different statuses and types
        await device_service.create_device(
            "active-sensor", "Active Sensor", DeviceType.SENSOR
        )
        await device_service.create_device(
            "offline-sensor", "Offline Sensor", DeviceType.SENSOR
        )
        await device_service.create_device(
            "active-actuator", "Active Actuator", DeviceType.ACTUATOR
        )

        # Update statuses
        await device_service.update_device_status("active-sensor", DeviceStatus.ACTIVE)
        await device_service.update_device_status(
            "active-actuator", DeviceStatus.ACTIVE
        )

        stats = await device_service.get_device_statistics()

        assert stats["total_devices"] == 3
        assert stats["active_devices"] == 2
        assert stats["offline_devices"] == 1
        assert stats["sensors"] == 2
        assert stats["actuators"] == 1
        assert stats["devices_by_status"]["active"] == 2
        assert stats["devices_by_status"]["offline"] == 1
        assert stats["devices_by_type"]["sensor"] == 2
        assert stats["devices_by_type"]["actuator"] == 1

    @pytest.mark.asyncio
    async def test_search_devices_by_name(self, device_service):
        """Test searching devices by name"""
        # Create devices with different names
        await device_service.create_device(
            "temp-sensor-1", "Temperature Sensor 1", DeviceType.SENSOR
        )
        await device_service.create_device(
            "temp-sensor-2", "Temperature Sensor 2", DeviceType.SENSOR
        )
        await device_service.create_device(
            "humidity-sensor", "Humidity Sensor", DeviceType.SENSOR
        )

        # Search for devices with "Temperature" in name
        temp_devices = await device_service.search_devices("Temperature")

        assert len(temp_devices) == 2
        assert all("Temperature" in device.name for device in temp_devices)

        # Search for devices with "Humidity" in name
        humidity_devices = await device_service.search_devices("Humidity")

        assert len(humidity_devices) == 1
        assert humidity_devices[0].name == "Humidity Sensor"

    @pytest.mark.asyncio
    async def test_search_devices_by_location(self, device_service):
        """Test searching devices by location"""
        # Create devices with different locations
        await device_service.create_device(
            "nyc-device",
            "NYC Device",
            DeviceType.SENSOR,
            location={"city": "New York", "country": "USA"},
        )
        await device_service.create_device(
            "london-device",
            "London Device",
            DeviceType.SENSOR,
            location={"city": "London", "country": "UK"},
        )

        # Search for devices in New York
        nyc_devices = await device_service.search_devices_by_location("New York")

        assert len(nyc_devices) == 1
        assert nyc_devices[0].location["city"] == "New York"

    @pytest.mark.asyncio
    async def test_batch_create_devices(self, device_service, multiple_devices_data):
        """Test creating multiple devices in batch"""
        devices_data = [
            {
                "device_id": device["device_id"],
                "name": device["name"],
                "device_type": device["device_type"],
                "manufacturer": device["manufacturer"],
                "model": device["model"],
                "location": device["location"],
            }
            for device in multiple_devices_data
        ]

        created_devices = await device_service.batch_create_devices(devices_data)

        assert len(created_devices) == 5
        for i, device in enumerate(created_devices):
            assert device.device_id == multiple_devices_data[i]["device_id"]
            assert device.name == multiple_devices_data[i]["name"]

    @pytest.mark.asyncio
    async def test_batch_update_status(self, device_service):
        """Test updating status for multiple devices"""
        # Create devices
        device_ids = []
        for i in range(3):
            device_id = f"batch-update-device-{i}"
            device_ids.append(device_id)
            await device_service.create_device(
                device_id, f"Device {i}", DeviceType.SENSOR
            )

        # Update all devices to ACTIVE status
        updated_count = await device_service.batch_update_device_status(
            device_ids, DeviceStatus.ACTIVE
        )

        assert updated_count == 3

        # Verify all devices are updated
        for device_id in device_ids:
            device = await device_service.get_device_by_id(device_id)
            assert device.status == DeviceStatus.ACTIVE
