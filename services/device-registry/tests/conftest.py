"""
Device Registry Test Configuration
Provides shared fixtures for device registry tests
"""

import asyncio

import pytest
import redis
from app.config import settings
from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Test Database Configuration
TEST_DATABASE_URL = "postgresql://iot_user:iot_password@localhost:5433/iot_test_db"
TEST_REDIS_URL = "redis://localhost:6380/15"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)
    yield engine

    # Drop all tables after tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db_session(test_engine):
    """Create test database session"""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    # Create connection and transaction
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create session
    session = TestingSessionLocal(bind=connection)

    yield session

    # Cleanup
    session.close()
    transaction.rollback()
    connection.close()


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
def test_client(test_db_session):
    """Create test client with database dependency override"""

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Clean up dependency override
    app.dependency_overrides.clear()


@pytest.fixture
def sample_device_data():
    """Sample device data for testing"""
    return {
        "device_id": "test-device-001",
        "name": "Test Temperature Sensor",
        "device_type": "sensor",
        "manufacturer": "TestCorp",
        "model": "TC-1000",
        "firmware_version": "1.0.0",
        "location": {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "address": "123 Test St, Test City, NY 10001",
        },
        "metadata": {
            "sensor_type": "temperature",
            "range": {"min": -40, "max": 125},
            "accuracy": 0.5,
            "unit": "celsius",
        },
    }


@pytest.fixture
def sample_device_token():
    """Sample JWT token for testing"""
    # This should match the format used in your auth service
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkZXZpY2VfaWQiOiJ0ZXN0LWRldmljZS0wMDEiLCJleHAiOjk5OTk5OTk5OTl9.test"


@pytest.fixture
def authenticated_client(test_client, sample_device_token):
    """Create authenticated test client"""
    test_client.headers.update({"Authorization": f"Bearer {sample_device_token}"})
    return test_client


@pytest.fixture
def multiple_devices_data():
    """Multiple device samples for batch operations"""
    return [
        {
            "device_id": f"test-device-{i:03d}",
            "name": f"Test Sensor {i}",
            "device_type": "sensor",
            "manufacturer": "TestCorp",
            "model": "TC-1000",
            "firmware_version": "1.0.{i}",
            "location": {
                "latitude": 40.7128 + (i * 0.01),
                "longitude": -74.0060 + (i * 0.01),
                "address": f"{i} Test St, Test City, NY 1000{i}",
            },
            "metadata": {
                "sensor_type": "temperature" if i % 2 == 0 else "humidity",
                "range": {"min": -40, "max": 125},
                "accuracy": 0.5 + (i * 0.1),
                "unit": "celsius" if i % 2 == 0 else "percent",
            },
        }
        for i in range(1, 6)  # 5 devices
    ]


@pytest.fixture
def invalid_device_data():
    """Invalid device data for negative testing"""
    return [
        {
            # Missing required device_id
            "name": "Invalid Device",
            "device_type": "sensor",
        },
        {
            "device_id": "",  # Empty device_id
            "name": "Invalid Device",
            "device_type": "sensor",
        },
        {
            "device_id": "device@invalid",  # Invalid characters
            "name": "Invalid Device",
            "device_type": "sensor",
        },
        {
            "device_id": "valid-id",
            "name": "Invalid Device",
            "device_type": "invalid_type",  # Invalid device type
        },
    ]


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: Mark test as a unit test")
    config.addinivalue_line("markers", "integration: Mark test as an integration test")
    config.addinivalue_line("markers", "e2e: Mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: Mark test as slow running")


@pytest.fixture
def mock_kafka_producer(monkeypatch):
    """Mock Kafka producer for testing"""

    class MockProducer:
        async def send(self, topic, value, key=None):
            return {"topic": topic, "key": key, "value": value}

        async def close(self):
            pass

    return MockProducer()
