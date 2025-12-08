"""
Unit Tests for Device Models
"""

import uuid
from datetime import datetime

import pytest
from app.models.device import Device, DeviceMetrics, DeviceStatus, DeviceType
from sqlalchemy.exc import IntegrityError


class TestDeviceModel:
    """Test Device model"""

    def test_device_creation(self, test_db_session):
        """Test creating a device with valid data"""
        device = Device(
            device_id="test-device-001",
            name="Test Temperature Sensor",
            device_type=DeviceType.SENSOR,
            manufacturer="TestCorp",
            model="TC-1000",
            firmware_version="1.0.0",
            status=DeviceStatus.ACTIVE,
            location={"latitude": 40.7128, "longitude": -74.0060},
            metadata={"sensor_type": "temperature", "accuracy": 0.5},
        )

        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        assert device.id is not None
        assert isinstance(device.id, uuid.UUID)
        assert device.device_id == "test-device-001"
        assert device.name == "Test Temperature Sensor"
        assert device.device_type == DeviceType.SENSOR
        assert device.status == DeviceStatus.ACTIVE
        assert device.created_at is not None
        assert isinstance(device.created_at, datetime)
        assert device.updated_at is not None

    def test_device_creation_minimal_fields(self, test_db_session):
        """Test creating a device with minimal required fields"""
        device = Device(
            device_id="minimal-device",
            name="Minimal Device",
            device_type=DeviceType.ACTUATOR,
        )

        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        assert device.device_id == "minimal-device"
        assert device.device_type == DeviceType.ACTUATOR
        assert device.status == DeviceStatus.OFFLINE  # Default status
        assert device.location is None
        assert device.metadata is None
        assert device.manufacturer is None

    def test_device_unique_device_id(self, test_db_session):
        """Test device_id must be unique"""
        device1 = Device(
            device_id="duplicate-device", name="Device 1", device_type=DeviceType.SENSOR
        )

        device2 = Device(
            device_id="duplicate-device",  # Same device_id
            name="Device 2",
            device_type=DeviceType.SENSOR,
        )

        test_db_session.add(device1)
        test_db_session.commit()

        test_db_session.add(device2)
        with pytest.raises(IntegrityError):
            test_db_session.commit()

    def test_device_status_enum(self, test_db_session):
        """Test device status enum values"""
        device = Device(
            device_id="status-test-device",
            name="Status Test Device",
            device_type=DeviceType.SENSOR,
        )

        # Test all valid status values
        for status in DeviceStatus:
            device.status = status
            test_db_session.add(device)
            test_db_session.commit()

            assert device.status == status
            test_db_session.delete(device)
            test_db_session.commit()

    def test_device_type_enum(self, test_db_session):
        """Test device type enum values"""
        device = Device(device_id="type-test-device", name="Type Test Device")

        # Test all valid device types
        for device_type in DeviceType:
            device.device_type = device_type
            test_db_session.add(device)
            test_db_session.commit()

            assert device.device_type == device_type
            test_db_session.delete(device)
            test_db_session.commit()

    def test_device_json_fields(self, test_db_session):
        """Test JSON fields (location and metadata)"""
        location_data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "address": "123 Test St, Test City, NY 10001",
            "floor": 2,
            "room": "Lab-A",
        }

        metadata_data = {
            "sensor_type": "temperature",
            "range": {"min": -40, "max": 125},
            "accuracy": 0.5,
            "unit": "celsius",
            "calibration_date": "2024-01-01",
            "maintenance_interval": 30,
        }

        device = Device(
            device_id="json-test-device",
            name="JSON Test Device",
            device_type=DeviceType.SENSOR,
            location=location_data,
            metadata=metadata_data,
        )

        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        assert device.location == location_data
        assert device.metadata == metadata_data
        assert device.location["latitude"] == 40.7128
        assert device.metadata["sensor_type"] == "temperature"

    def test_device_update_timestamp(self, test_db_session):
        """Test updated_at timestamp changes on update"""
        device = Device(
            device_id="timestamp-test-device",
            name="Original Name",
            device_type=DeviceType.SENSOR,
        )

        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        original_updated_at = device.updated_at

        # Wait a bit to ensure timestamp difference
        import time

        time.sleep(0.01)

        # Update the device
        device.name = "Updated Name"
        device.status = DeviceStatus.ACTIVE
        test_db_session.commit()
        test_db_session.refresh(device)

        assert device.updated_at > original_updated_at

    def test_device_str_representation(self, test_db_session):
        """Test device string representation"""
        device = Device(
            device_id="string-test-device",
            name="String Test Device",
            device_type=DeviceType.SENSOR,
        )

        test_db_session.add(device)
        test_db_session.commit()

        str_repr = str(device)
        assert device.device_id in str_repr
        assert device.name in str_repr

    def test_device_repr(self, test_db_session):
        """Test device repr"""
        device = Device(
            device_id="repr-test-device",
            name="Repr Test Device",
            device_type=DeviceType.SENSOR,
        )

        test_db_session.add(device)
        test_db_session.commit()

        repr_str = repr(device)
        assert "Device" in repr_str
        assert device.device_id in repr_str


class TestDeviceMetricsModel:
    """Test DeviceMetrics model"""

    def test_device_metrics_creation(self, test_db_session, sample_device_data):
        """Test creating device metrics"""
        # First create a device
        device = Device(
            device_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            device_type=DeviceType.SENSOR,
        )
        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        # Create metrics for the device
        metrics = DeviceMetrics(
            device_id=device.id,
            metric_name="temperature",
            value=23.5,
            unit="celsius",
            timestamp=datetime.utcnow(),
        )

        test_db_session.add(metrics)
        test_db_session.commit()
        test_db_session.refresh(metrics)

        assert metrics.id is not None
        assert isinstance(metrics.id, uuid.UUID)
        assert metrics.device_id == device.id
        assert metrics.metric_name == "temperature"
        assert metrics.value == 23.5
        assert metrics.unit == "celsius"
        assert metrics.timestamp is not None
        assert isinstance(metrics.timestamp, datetime)

    def test_device_metrics_relationship(self, test_db_session):
        """Test relationship between Device and DeviceMetrics"""
        device = Device(
            device_id="metrics-rel-device",
            name="Metrics Relationship Device",
            device_type=DeviceType.SENSOR,
        )
        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        # Add multiple metrics
        metrics_data = [
            {"metric_name": "temperature", "value": 23.5, "unit": "celsius"},
            {"metric_name": "humidity", "value": 65.2, "unit": "percent"},
            {"metric_name": "pressure", "value": 1013.25, "unit": "hPa"},
        ]

        for metric_data in metrics_data:
            metrics = DeviceMetrics(
                device_id=device.id, timestamp=datetime.utcnow(), **metric_data
            )
            test_db_session.add(metrics)

        test_db_session.commit()

        # Test relationship
        device_metrics = (
            test_db_session.query(DeviceMetrics).filter_by(device_id=device.id).all()
        )
        assert len(device_metrics) == 3

        # Test accessing device from metrics
        for metric in device_metrics:
            assert metric.device.device_id == "metrics-rel-device"

    def test_device_metrics_optional_fields(self, test_db_session):
        """Test device metrics with optional fields"""
        device = Device(
            device_id="optional-metrics-device",
            name="Optional Metrics Device",
            device_type=DeviceType.SENSOR,
        )
        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        # Create metrics without unit
        metrics = DeviceMetrics(
            device_id=device.id,
            metric_name="cpu_usage",
            value=75.5,
            timestamp=datetime.utcnow(),
            # unit is optional
        )

        test_db_session.add(metrics)
        test_db_session.commit()
        test_db_session.refresh(metrics)

        assert metrics.unit is None

    def test_device_metrics_str_representation(self, test_db_session):
        """Test device metrics string representation"""
        device = Device(
            device_id="metrics-str-device",
            name="Metrics String Device",
            device_type=DeviceType.SENSOR,
        )
        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        metrics = DeviceMetrics(
            device_id=device.id,
            metric_name="temperature",
            value=23.5,
            unit="celsius",
            timestamp=datetime.utcnow(),
        )
        test_db_session.add(metrics)
        test_db_session.commit()

        str_repr = str(metrics)
        assert metrics.metric_name in str_repr
        assert str(metrics.value) in str_repr

    @pytest.mark.parametrize(
        "metric_value,expected",
        [
            (23.5, 23.5),
            (0, 0),
            (-10.5, -10.5),
            (1000.123456, 1000.123456),
        ],
    )
    def test_device_metrics_value_types(self, test_db_session, metric_value, expected):
        """Test device metrics with different value types"""
        device = Device(
            device_id="value-test-device",
            name="Value Test Device",
            device_type=DeviceType.SENSOR,
        )
        test_db_session.add(device)
        test_db_session.commit()
        test_db_session.refresh(device)

        metrics = DeviceMetrics(
            device_id=device.id,
            metric_name="test_metric",
            value=metric_value,
            timestamp=datetime.utcnow(),
        )
        test_db_session.add(metrics)
        test_db_session.commit()
        test_db_session.refresh(metrics)

        assert metrics.value == expected
