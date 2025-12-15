"""
Data Ingestion Test Configuration
Provides shared fixtures for data ingestion tests
"""

import asyncio
import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
import redis
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

# Test Redis Configuration
TEST_REDIS_URL = "redis://localhost:6380/15"
TEST_KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_redis():
    """Create test Redis connection"""
    redis_client = redis.from_url(TEST_REDIS_URL, decode_responses=True)

    # Clear test database before tests
    redis_client.flushdb()

    yield redis_client

    # Clear test database after tests
    redis_client.flushdb()
    redis_client.close()


@pytest.fixture
def test_client():
    """Create test client for data ingestion service"""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_device_data():
    """Sample device data for testing"""
    return {
        "device_id": "test-sensor-001",
        "device_type": "temperature",
        "name": "Test Temperature Sensor",
        "location": "Room 101",
        "metadata": {
            "sensor_range": {"min": -40, "max": 125},
            "accuracy": 0.5,
            "unit": "celsius",
        },
    }


@pytest.fixture
def sample_sensor_data():
    """Sample sensor data points for testing"""
    return [
        {
            "metric_name": "temperature",
            "value": 23.5,
            "timestamp": "2024-01-01T12:00:00Z",
        },
        {"metric_name": "humidity", "value": 65.2, "timestamp": "2024-01-01T12:00:00Z"},
        {
            "metric_name": "pressure",
            "value": 1013.25,
            "timestamp": "2024-01-01T12:00:00Z",
        },
    ]


@pytest.fixture
def sample_ingestion_data(sample_device_data, sample_sensor_data):
    """Complete sample ingestion request"""
    return {"device_id": sample_device_data["device_id"], "data": sample_sensor_data}


@pytest.fixture
def batch_ingestion_data():
    """Sample batch ingestion data"""
    return {
        "batch_id": "batch-001",
        "timestamp": "2024-01-01T12:00:00Z",
        "devices": [
            {
                "device_id": f"sensor-{i:03d}",
                "data": [
                    {
                        "metric_name": "temperature" if i % 2 == 0 else "humidity",
                        "value": 20.0 + (i * 2.5),
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                ],
            }
            for i in range(1, 6)  # 5 devices
        ],
    }


@pytest.fixture
def invalid_ingestion_data():
    """Invalid ingestion data for negative testing"""
    return [
        {
            # Missing device_id
            "data": [
                {
                    "metric_name": "temperature",
                    "value": 25.0,
                    "timestamp": "2024-01-01T12:00:00Z",
                }
            ]
        },
        {
            "device_id": "",  # Empty device_id
            "data": [
                {
                    "metric_name": "temperature",
                    "value": 25.0,
                    "timestamp": "2024-01-01T12:00:00Z",
                }
            ],
        },
        {"device_id": "test-device", "data": []},  # Empty data array
        {
            "device_id": "test-device",
            "data": [
                {
                    # Missing metric_name
                    "value": 25.0,
                    "timestamp": "2024-01-01T12:00:00Z",
                }
            ],
        },
        {
            "device_id": "test-device",
            "data": [
                {
                    "metric_name": "temperature",
                    "value": "invalid_value",  # Invalid value type
                    "timestamp": "2024-01-01T12:00:00Z",
                }
            ],
        },
    ]


@pytest.fixture
def mock_kafka_producer(monkeypatch):
    """Mock Kafka producer for testing"""

    class MockKafkaProducer:
        def __init__(self, *args, **kwargs):
            self.messages = []

        async def send_and_wait(self, topic, value=None, key=None):
            message = {
                "topic": topic,
                "key": key,
                "value": json.loads(value) if isinstance(value, str) else value,
            }
            self.messages.append(message)
            return message

        async def start(self):
            pass

        async def stop(self):
            pass

        async def close(self):
            pass

    return MockKafkaProducer()


@pytest.fixture
def mock_mqtt_client(monkeypatch):
    """Mock MQTT client for testing"""

    class MockMQTTClient:
        def __init__(self, *args, **kwargs):
            self.connected = False
            self.messages = []

        async def connect(self, broker_host, broker_port=1883):
            self.connected = True

        async def disconnect(self):
            self.connected = False

        async def publish(self, topic, payload, qos=0):
            self.messages.append({"topic": topic, "payload": payload, "qos": qos})

        async def subscribe(self, topic):
            pass

    return MockMQTTClient()


@pytest.fixture
def mock_influxdb_client(monkeypatch):
    """Mock InfluxDB client for testing"""

    class MockInfluxDBClient:
        def __init__(self, *args, **kwargs):
            self.points = []

        async def write(self, bucket, org, record):
            self.points.append({"bucket": bucket, "org": org, "record": record})

        async def query(self, query):
            return {"result": "mock_data"}

        async def close(self):
            pass

    return MockInfluxDBClient()


@pytest.fixture
def authenticated_client(test_client, sample_device_data):
    """Create authenticated test client"""
    # Mock device authentication
    auth_token = f"Bearer device-token-{sample_device_data['device_id']}"
    test_client.headers.update(
        {"Authorization": auth_token, "X-Device-ID": sample_device_data["device_id"]}
    )
    return test_client


@pytest.fixture
def mock_device_registry_service(monkeypatch):
    """Mock device registry service for authentication"""

    class MockDeviceRegistry:
        async def authenticate_device(self, device_id: str, token: str) -> dict:
            # Return mock device data for valid devices
            if device_id.startswith("test-") or device_id.startswith("sensor-"):
                return {
                    "device_id": device_id,
                    "status": "active",
                    "authenticated": True,
                }
            return {"authenticated": False}

        async def get_device_info(self, device_id: str) -> dict:
            if device_id == "test-device-invalid":
                return None
            return {
                "device_id": device_id,
                "name": f"Test Device {device_id}",
                "type": "sensor",
                "status": "active",
            }

    return MockDeviceRegistry()


@pytest.fixture
def performance_test_data():
    """Large dataset for performance testing"""
    return {
        "device_id": "perf-test-device",
        "data": [
            {
                "metric_name": "cpu_usage",
                "value": 50.0 + (i % 50),
                "timestamp": f"2024-01-01T12:{i//60:02d}:{i%60:02d}Z",
            }
            for i in range(1000)  # 1000 data points
        ],
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: Mark test as a unit test")
    config.addinivalue_line("markers", "integration: Mark test as an integration test")
    config.addinivalue_line("markers", "e2e: Mark test as an end-to-end test")
    config.addinivalue_line("markers", "performance: Mark test as a performance test")
    config.addinivalue_line("markers", "slow: Mark test as slow running")


@pytest.fixture
def alert_threshold_data():
    """Sample alert threshold configuration"""
    return {
        "device_id": "test-alert-device",
        "alerts": [
            {
                "metric_name": "temperature",
                "condition": "greater_than",
                "threshold": 80.0,
                "severity": "high",
                "message": "Temperature too high",
            },
            {
                "metric_name": "humidity",
                "condition": "less_than",
                "threshold": 30.0,
                "severity": "medium",
                "message": "Humidity too low",
            },
        ],
    }
