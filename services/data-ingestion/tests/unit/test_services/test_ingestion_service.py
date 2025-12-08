"""
Unit Tests for Ingestion Service Business Logic
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from app.services.ingestion_service import DataIngestionService


class TestDataIngestionService:
    """Test Ingestion Service business logic"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        return Mock()

    @pytest.fixture
    def mock_kafka_producer(self):
        """Mock Kafka producer"""
        producer = Mock()
        producer.send_and_wait = AsyncMock()
        return producer

    @pytest.fixture
    def mock_device_registry(self):
        """Mock device registry service"""
        registry = Mock()
        registry.authenticate_device = AsyncMock()
        registry.get_device_info = AsyncMock()
        return registry

    @pytest.fixture
    def ingestion_service(self, mock_redis, mock_kafka_producer, mock_device_registry):
        """Create ingestion service instance with mocked dependencies"""
        # Create mock services
        mock_kafka_service = Mock()
        mock_redis_service = Mock()

        return DataIngestionService(
            kafka_producer=mock_kafka_service,
            redis_service=mock_redis_service
        )

    @pytest.mark.asyncio
    async def test_ingest_single_data_point_success(
        self, ingestion_service, mock_device_registry, mock_kafka_producer, sample_ingestion_data
    ):
        """Test successful single data point ingestion"""
        # Mock device authentication success
        mock_device_registry.authenticate_device.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "authenticated": True,
            "status": "active"
        }

        # Mock device info
        mock_device_registry.get_device_info.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "name": "Test Sensor",
            "type": "sensor",
            "location": {"latitude": 40.7128, "longitude": -74.0060}
        }

        # Test ingestion
        result = await ingestion_service.ingest_data(
            device_id=sample_ingestion_data["device_id"],
            data=sample_ingestion_data["data"],
            auth_token="valid-token"
        )

        assert result["success"] is True
        assert result["device_id"] == sample_ingestion_data["device_id"]
        assert result["data_points_ingested"] == len(sample_ingestion_data["data"])

        # Verify device authentication was called
        mock_device_registry.authenticate_device.assert_called_once_with(
            sample_ingestion_data["device_id"], "valid-token"
        )

        # Verify device info was fetched
        mock_device_registry.get_device_info.assert_called_once_with(
            sample_ingestion_data["device_id"]
        )

        # Verify Kafka producer was called for each data point
        assert mock_kafka_producer.send_and_wait.call_count == len(sample_ingestion_data["data"])

    @pytest.mark.asyncio
    async def test_ingest_data_device_authentication_failure(
        self, ingestion_service, mock_device_registry, sample_ingestion_data
    ):
        """Test ingestion with failed device authentication"""
        # Mock device authentication failure
        mock_device_registry.authenticate_device.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "authenticated": False,
            "error": "Invalid credentials"
        }

        # Test ingestion should fail
        result = await ingestion_service.ingest_data(
            device_id=sample_ingestion_data["device_id"],
            data=sample_ingestion_data["data"],
            auth_token="invalid-token"
        )

        assert result["success"] is False
        assert "authentication_failed" in result
        assert result["error"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_ingest_data_device_not_found(
        self, ingestion_service, mock_device_registry, sample_ingestion_data
    ):
        """Test ingestion when device is not found in registry"""
        # Mock device authentication success but device not found
        mock_device_registry.authenticate_device.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "authenticated": True,
            "status": "active"
        }
        mock_device_registry.get_device_info.return_value = None

        # Test ingestion should fail
        result = await ingestion_service.ingest_data(
            device_id=sample_ingestion_data["device_id"],
            data=sample_ingestion_data["data"],
            auth_token="valid-token"
        )

        assert result["success"] is False
        assert "device_not_found" in result

    @pytest.mark.asyncio
    async def test_ingest_batch_data_success(
        self, ingestion_service, mock_device_registry, mock_kafka_producer, batch_ingestion_data
    ):
        """Test successful batch data ingestion"""
        # Mock device authentication success for all devices
        mock_device_registry.authenticate_device.return_value = {
            "authenticated": True,
            "status": "active"
        }
        mock_device_registry.get_device_info.return_value = {
            "type": "sensor",
            "location": {"latitude": 40.7128, "longitude": -74.0060}
        }

        # Test batch ingestion
        result = await ingestion_service.ingest_batch_data(
            batch_data=batch_ingestion_data,
            auth_token="valid-token"
        )

        assert result["success"] is True
        assert result["batch_id"] == batch_ingestion_data["batch_id"]
        assert result["devices_processed"] == len(batch_ingestion_data["devices"])
        assert result["total_data_points"] == sum(
            len(device["data"]) for device in batch_ingestion_data["devices"]
        )

    @pytest.mark.asyncio
    async def test_ingest_data_validation_failure(
        self, ingestion_service, sample_ingestion_data
    ):
        """Test ingestion with invalid data structure"""
        invalid_data = [
            {"metric_name": "", "value": 25.0, "timestamp": "2024-01-01T12:00:00Z"}  # Empty metric name
        ]

        result = await ingestion_service.ingest_data(
            device_id=sample_ingestion_data["device_id"],
            data=invalid_data,
            auth_token="valid-token"
        )

        assert result["success"] is False
        assert "validation_error" in result

    @pytest.mark.asyncio
    async def test_ingest_data_enrichment(
        self, ingestion_service, mock_device_registry, mock_kafka_producer, sample_ingestion_data
    ):
        """Test that data is properly enriched with device info"""
        # Mock device authentication and info
        mock_device_registry.authenticate_device.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "authenticated": True,
            "status": "active"
        }
        mock_device_registry.get_device_info.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "name": "Temperature Sensor 001",
            "type": "sensor",
            "location": {"latitude": 40.7128, "longitude": -74.0060, "room": "Server Room A"},
            "metadata": {"sensor_type": "DHT22", "calibration_date": "2024-01-01"}
        }

        # Test ingestion
        await ingestion_service.ingest_data(
            device_id=sample_ingestion_data["device_id"],
            data=sample_ingestion_data["data"],
            auth_token="valid-token"
        )

        # Verify enriched data was sent to Kafka
        for call in mock_kafka_producer.send_and_wait.call_args_list:
            sent_data = call[1]["value"]
            if isinstance(sent_data, str):
                sent_data = json.loads(sent_data)

            # Check that device info is included in enriched data
            assert "device_info" in sent_data
            assert sent_data["device_info"]["name"] == "Temperature Sensor 001"
            assert sent_data["device_info"]["location"]["room"] == "Server Room A"
            assert "ingestion_timestamp" in sent_data

    @pytest.mark.asyncio
    async def test_ingest_data_kafka_failure(
        self, ingestion_service, mock_device_registry, mock_kafka_producer, sample_ingestion_data
    ):
        """Test handling of Kafka producer failure"""
        # Mock device authentication success
        mock_device_registry.authenticate_device.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "authenticated": True,
            "status": "active"
        }
        mock_device_registry.get_device_info.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "type": "sensor"
        }

        # Mock Kafka failure
        mock_kafka_producer.send_and_wait.side_effect = Exception("Kafka connection failed")

        # Test ingestion should handle Kafka failure gracefully
        result = await ingestion_service.ingest_data(
            device_id=sample_ingestion_data["device_id"],
            data=sample_ingestion_data["data"],
            auth_token="valid-token"
        )

        assert result["success"] is False
        assert "kafka_error" in result
        assert "Kafka connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_ingest_data_with_alerts(
        self, ingestion_service, mock_device_registry, mock_kafka_producer, sample_ingestion_data
    ):
        """Test ingestion with alert generation"""
        # Create data that should trigger alerts
        alert_data = [
            {
                "metric_name": "temperature",
                "value": 95.0,  # High temperature alert
                "timestamp": "2024-01-01T12:00:00Z"
            },
            {
                "metric_name": "humidity",
                "value": 15.0,  # Low humidity alert
                "timestamp": "2024-01-01T12:00:00Z"
            }
        ]

        # Mock device authentication and info with alert thresholds
        mock_device_registry.authenticate_device.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "authenticated": True,
            "status": "active"
        }
        mock_device_registry.get_device_info.return_value = {
            "device_id": sample_ingestion_data["device_id"],
            "type": "sensor",
            "alert_thresholds": {
                "temperature": {"max": 80.0, "min": 0.0},
                "humidity": {"max": 100.0, "min": 30.0}
            }
        }

        # Test ingestion with alert generation
        result = await ingestion_service.ingest_data(
            device_id=sample_ingestion_data["device_id"],
            data=alert_data,
            auth_token="valid-token"
        )

        assert result["success"] is True
        assert result["alerts_generated"] == 2

        # Verify alert messages were sent to Kafka
        alert_calls = [
            call for call in mock_kafka_producer.send_and_wait.call_args_list
            if call[0][0] == "iot-alerts"  # Alert topic
        ]
        assert len(alert_calls) == 2

    @pytest.mark.asyncio
    async def test_get_device_statistics(
        self, ingestion_service, mock_redis, sample_device_data
    ):
        """Test getting device ingestion statistics"""
        device_id = sample_device_data["device_id"]

        # Mock Redis statistics data
        mock_redis.hgetall.return_value = {
            "total_ingested": "150",
            "last_ingestion": "2024-01-01T12:00:00Z",
            "avg_ingestion_rate": "2.5",
            "total_errors": "3",
            "last_error": "Invalid data format"
        }

        stats = await ingestion_service.get_device_statistics(device_id)

        assert stats["device_id"] == device_id
        assert stats["total_ingested"] == 150
        assert stats["last_ingestion"] == "2024-01-01T12:00:00Z"
        assert stats["avg_ingestion_rate"] == 2.5
        assert stats["total_errors"] == 3
        assert stats["last_error"] == "Invalid data format"

        # Verify Redis was called with correct key
        mock_redis.hgetall.assert_called_once_with(f"device_stats:{device_id}")

    @pytest.mark.asyncio
    async def test_update_device_statistics(
        self, ingestion_service, mock_redis, sample_device_data
    ):
        """Test updating device statistics"""
        device_id = sample_device_data["device_id"]

        # Mock Redis operations
        mock_redis.incr.return_value = 1
        mock_redis.set.return_value = True
        mock_redis.hset.return_value = True

        await ingestion_service.update_device_statistics(
            device_id=device_id,
            data_points_count=5,
            success=True
        )

        # Verify Redis was called to update statistics
        mock_redis.incr.assert_called_with(f"device_stats:{device_id}:total_ingested", 5)
        mock_redis.set.assert_called_with(f"device_stats:{device_id}:last_ingestion", pytest.approx(datetime.utcnow().timestamp(), rel=1e6))

    @pytest.mark.asyncio
    async def test_process_data_point_transformation(
        self, ingestion_service, sample_device_data
    ):
        """Test data point transformation and enrichment"""
        device_id = sample_device_data["device_id"]
        raw_data_point = {
            "metric_name": "temperature",
            "value": 23.5,
            "timestamp": "2024-01-01T12:00:00Z"
        }

        device_info = {
            "device_id": device_id,
            "name": "Temperature Sensor",
            "type": "sensor",
            "location": {"latitude": 40.7128, "longitude": -74.0060},
            "metadata": {"sensor_type": "DHT22"}
        }

        # Test data transformation
        enriched_data = ingestion_service._transform_data_point(
            raw_data_point, device_info
        )

        assert enriched_data["metric_name"] == raw_data_point["metric_name"]
        assert enriched_data["value"] == raw_data_point["value"]
        assert enriched_data["timestamp"] == raw_data_point["timestamp"]
        assert enriched_data["device_id"] == device_id
        assert "device_info" in enriched_data
        assert enriched_data["device_info"]["name"] == "Temperature Sensor"
        assert "ingestion_timestamp" in enriched_data
        assert isinstance(enriched_data["ingestion_timestamp"], str)

    @pytest.mark.asyncio
    async def test_validate_data_point(self, ingestion_service):
        """Test data point validation"""
        valid_data_point = {
            "metric_name": "temperature",
            "value": 23.5,
            "timestamp": "2024-01-01T12:00:00Z"
        }

        # Test valid data point
        is_valid, error = ingestion_service._validate_data_point(valid_data_point)
        assert is_valid is True
        assert error is None

        # Test invalid data point (missing fields)
        invalid_data_point = {
            "metric_name": "temperature",
            "value": 23.5
            # Missing timestamp
        }

        is_valid, error = ingestion_service._validate_data_point(invalid_data_point)
        assert is_valid is False
        assert "timestamp" in error

        # Test invalid timestamp format
        invalid_timestamp_data = {
            "metric_name": "temperature",
            "value": 23.5,
            "timestamp": "invalid-timestamp"
        }

        is_valid, error = ingestion_service._validate_data_point(invalid_timestamp_data)
        assert is_valid is False
        assert "Invalid timestamp format" in error

    @pytest.mark.asyncio
    async def test_get_ingestion_health_status(
        self, ingestion_service, mock_redis
    ):
        """Test getting ingestion service health status"""
        # Mock Redis health data
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {"connected_clients": 10, "used_memory": "1024k"}

        # Mock Kafka producer health
        mock_kafka_health = {
            "connected": True,
            "bootstrap_servers": ["localhost:9092"],
            "topic_count": 5
        }

        with patch.object(ingestion_service, '_check_kafka_health', return_value=mock_kafka_health):
            health_status = await ingestion_service.get_health_status()

        assert health_status["status"] == "healthy"
        assert health_status["redis"]["connected"] is True
        assert health_status["kafka"]["connected"] is True
        assert "uptime" in health_status

    @pytest.mark.asyncio
    async def test_cleanup_old_device_data(
        self, ingestion_service, mock_redis
    ):
        """Test cleanup of old device data"""
        # Mock Redis operations for cleanup
        mock_redis.scan_iter.return_value = [
            b"device_stats:old-device-001",
            b"device_stats:old-device-002"
        ]
        mock_redis.delete.return_value = 2

        cleanup_result = await ingestion_service.cleanup_old_device_data(days=30)

        assert cleanup_result["cleaned_keys"] == 2
        assert len(cleanup_result["deleted_keys"]) == 2

        # Verify Redis operations
        mock_redis.scan_iter.assert_called()
        mock_redis.delete.assert_called_with(
            "device_stats:old-device-001",
            "device_stats:old-device-002"
        )