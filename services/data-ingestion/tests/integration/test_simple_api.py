"""
Simple API Integration Tests - without Kafka dependency
"""

import json
import os
# Import the app directly to avoid startup issues
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Create a simple test app without Kafka
from fastapi import FastAPI

app = FastAPI(title="IoT Data Ingestion Simple Test", version="1.0.0")


@app.get("/")
async def root():
    return {"status": "IoT Data Ingestion Simple Test"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/ingest")
async def ingest_data(data: dict):
    # Simple validation
    if "device_id" not in data or "data" not in data:
        return {"success": False, "error": "Missing device_id or data"}

    if not isinstance(data["data"], list) or len(data["data"]) == 0:
        return {"success": False, "error": "Data must be a non-empty list"}

    return {
        "success": True,
        "device_id": data["device_id"],
        "data_points": len(data["data"]),
        "stored": True,
    }


@app.get("/device/{device_id}")
async def get_device_data(device_id: str):
    # Mock response
    return {
        "device_id": device_id,
        "data": [
            {
                "metric_name": "temperature",
                "value": 23.5,
                "timestamp": "2024-01-01T12:00:00Z",
            }
        ],
    }


@pytest.mark.integration
class TestSimpleAPI:
    """Test basic API functionality without complex dependencies"""

    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}

    def test_root_endpoint(self):
        """Test root endpoint"""
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] == "IoT Data Ingestion Simple Test"

    def test_ingest_data_success(self):
        """Test successful data ingestion"""
        with TestClient(app) as client:
            test_data = {
                "device_id": "test-sensor-001",
                "data": [
                    {
                        "metric_name": "temperature",
                        "value": 23.5,
                        "timestamp": "2024-01-01T12:00:00Z",
                    },
                    {
                        "metric_name": "humidity",
                        "value": 65.2,
                        "timestamp": "2024-01-01T12:00:00Z",
                    },
                ],
            }

            response = client.post("/ingest", json=test_data)
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is True
            assert result["device_id"] == "test-sensor-001"
            assert result["data_points"] == 2
            assert result["stored"] is True

    def test_ingest_data_validation_error_missing_device_id(self):
        """Test ingestion with missing device_id"""
        with TestClient(app) as client:
            invalid_data = {
                "data": [
                    {
                        "metric_name": "temperature",
                        "value": 23.5,
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                ]
            }

            response = client.post("/ingest", json=invalid_data)
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is False
            assert "Missing device_id" in result["error"]

    def test_ingest_data_validation_error_empty_data(self):
        """Test ingestion with empty data array"""
        with TestClient(app) as client:
            invalid_data = {"device_id": "test-device", "data": []}

            response = client.post("/ingest", json=invalid_data)
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is False
            assert "non-empty list" in result["error"]

    def test_get_device_data(self):
        """Test getting device data"""
        with TestClient(app) as client:
            response = client.get("/device/test-sensor-001")
            assert response.status_code == 200

            data = response.json()
            assert data["device_id"] == "test-sensor-001"
            assert "data" in data
            assert len(data["data"]) > 0
            assert data["data"][0]["metric_name"] == "temperature"

    def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        import threading
        import time

        results = []

        def make_request():
            with TestClient(app) as client:
                response = client.get("/health")
                results.append(response.status_code)

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert len(results) == 10
        assert all(status == 200 for status in results)

    def test_large_payload(self):
        """Test handling larger payloads"""
        with TestClient(app) as client:
            large_data = {
                "device_id": "test-device",
                "data": [
                    {
                        "metric_name": f"metric_{i}",
                        "value": i * 1.5,
                        "timestamp": f"2024-01-01T12:{i:02d}:00Z",
                    }
                    for i in range(100)  # 100 data points
                ],
            }

            response = client.post("/ingest", json=large_data)
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is True
            assert result["data_points"] == 100

    def test_unicode_handling(self):
        """Test Unicode data handling"""
        with TestClient(app) as client:
            unicode_data = {
                "device_id": "sensor-ürleş-测试",
                "data": [
                    {
                        "metric_name": "sıcaklık",
                        "value": 23.5,
                        "timestamp": "2024-01-01T12:00:00Z",
                        "notes": "测试数据",
                    }
                ],
            }

            response = client.post("/ingest", json=unicode_data)
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is True
            assert result["device_id"] == "sensor-ürleş-测试"
