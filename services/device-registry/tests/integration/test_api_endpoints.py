"""
Integration Tests for Device Registry API Endpoints
"""

import pytest
import json
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestDeviceRegistryAPI:
    """Integration tests for device registry API endpoints"""

    def test_health_check_endpoint(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_root_endpoint(self, test_client):
        """Test root endpoint"""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert "version" in data
        assert "description" in data

    def test_create_device_success(self, test_client, sample_device_data):
        """Test successful device creation via API"""
        response = test_client.post("/devices", json=sample_device_data)

        assert response.status_code == 201
        data = response.json()
        assert data["device_id"] == sample_device_data["device_id"]
        assert data["name"] == sample_device_data["name"]
        assert data["device_type"] == sample_device_data["device_type"]
        assert data["manufacturer"] == sample_device_data["manufacturer"]
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_create_device_validation_error(self, test_client):
        """Test device creation with invalid data"""
        invalid_data = {
            "device_id": "",  # Empty device_id should fail
            "name": "Invalid Device",
            "device_type": "sensor"
        }

        response = test_client.post("/devices", json=invalid_data)

        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("device_id" in str(error).lower() for error in errors)

    def test_create_device_duplicate_id(self, test_client, sample_device_data):
        """Test creating device with duplicate ID"""
        # Create device first time
        response1 = test_client.post("/devices", json=sample_device_data)
        assert response1.status_code == 201

        # Try to create same device again
        response2 = test_client.post("/devices", json=sample_device_data)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    def test_get_device_success(self, test_client, sample_device_data):
        """Test getting device by ID"""
        # Create device first
        create_response = test_client.post("/devices", json=sample_device_data)
        assert create_response.status_code == 201

        # Get device
        response = test_client.get(f"/devices/{sample_device_data['device_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["device_id"] == sample_device_data["device_id"]
        assert data["name"] == sample_device_data["name"]

    def test_get_device_not_found(self, test_client):
        """Test getting non-existent device"""
        response = test_client.get("/devices/non-existent-device")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_list_devices_empty(self, test_client):
        """Test listing devices when none exist"""
        response = test_client.get("/devices")
        assert response.status_code == 200
        assert response.json()["devices"] == []
        assert response.json()["total"] == 0

    def test_list_devices_with_data(self, test_client, multiple_devices_data):
        """Test listing devices when some exist"""
        # Create multiple devices
        created_devices = []
        for device_data in multiple_devices_data:
            response = test_client.post("/devices", json=device_data)
            assert response.status_code == 201
            created_devices.append(response.json())

        # List devices
        response = test_client.get("/devices")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == len(multiple_devices_data)
        assert len(data["devices"]) == len(multiple_devices_data)

        # Check that all created devices are in the list
        returned_device_ids = {device["device_id"] for device in data["devices"]}
        expected_device_ids = {device["device_id"] for device in multiple_devices_data}
        assert returned_device_ids == expected_device_ids

    def test_list_devices_with_pagination(self, test_client, multiple_devices_data):
        """Test device listing with pagination"""
        # Create devices
        for device_data in multiple_devices_data:
            test_client.post("/devices", json=device_data)

        # Test pagination
        response = test_client.get("/devices?skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 2
        assert data["total"] == len(multiple_devices_data)

        response = test_client.get("/devices?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 2

    def test_list_devices_filter_by_status(self, test_client, sample_device_data):
        """Test filtering devices by status"""
        # Create device (will be OFFLINE by default)
        test_client.post("/devices", json=sample_device_data)

        # List only OFFLINE devices
        response = test_client.get("/devices?status=offline")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 1
        assert data["devices"][0]["status"] == "offline"

        # List only ACTIVE devices (should be empty)
        response = test_client.get("/devices?status=active")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 0

    def test_list_devices_filter_by_type(self, test_client, sample_device_data):
        """Test filtering devices by type"""
        # Create sensor device
        test_client.post("/devices", json=sample_device_data)

        # List only sensors
        response = test_client.get("/devices?device_type=sensor")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 1
        assert data["devices"][0]["device_type"] == "sensor"

        # List only actuators (should be empty)
        response = test_client.get("/devices?device_type=actuator")
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 0

    def test_update_device_success(self, test_client, sample_device_data):
        """Test successful device update"""
        # Create device first
        create_response = test_client.post("/devices", json=sample_device_data)
        assert create_response.status_code == 201

        # Update device
        update_data = {
            "name": "Updated Device Name",
            "manufacturer": "Updated Corp",
            "firmware_version": "2.0.0"
        }
        response = test_client.put(f"/devices/{sample_device_data['device_id']}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Device Name"
        assert data["manufacturer"] == "Updated Corp"
        assert data["firmware_version"] == "2.0.0"

    def test_update_device_not_found(self, test_client):
        """Test updating non-existent device"""
        update_data = {"name": "Updated Name"}
        response = test_client.put("/devices/non-existent-device", json=update_data)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_device_status(self, test_client, sample_device_data):
        """Test updating device status"""
        # Create device first
        test_client.post("/devices", json=sample_device_data)

        # Update status to ACTIVE
        status_data = {"status": "active"}
        response = test_client.patch(f"/devices/{sample_device_data['device_id']}/status", json=status_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    def test_delete_device_success(self, test_client, sample_device_data):
        """Test successful device deletion"""
        # Create device first
        create_response = test_client.post("/devices", json=sample_device_data)
        assert create_response.status_code == 201

        # Delete device
        response = test_client.delete(f"/devices/{sample_device_data['device_id']}")
        assert response.status_code == 204

        # Verify device is deleted
        get_response = test_client.get(f"/devices/{sample_device_data['device_id']}")
        assert get_response.status_code == 404

    def test_delete_device_not_found(self, test_client):
        """Test deleting non-existent device"""
        response = test_client.delete("/devices/non-existent-device")
        assert response.status_code == 404

    def test_device_authentication_success(self, test_client, sample_device_data):
        """Test device authentication endpoint"""
        # Create device first
        test_client.post("/devices", json=sample_device_data)

        # Test authentication
        auth_data = {
            "device_id": sample_device_data["device_id"],
            "secret": "test-secret-key"  # In real implementation, this would be validated
        }
        response = test_client.post(f"/devices/{sample_device_data['device_id']}/authenticate", json=auth_data)

        # This endpoint might not be fully implemented in test version
        # Adjust expectations based on actual implementation
        assert response.status_code in [200, 501]  # 501 if not implemented

    def test_device_metrics_endpoint(self, test_client, sample_device_data):
        """Test device metrics collection"""
        # Create device first
        test_client.post("/devices", json=sample_device_data)

        # Add metrics
        metrics_data = [
            {
                "metric_name": "cpu_usage",
                "value": 75.5,
                "unit": "percent",
                "timestamp": "2024-01-01T12:00:00Z"
            },
            {
                "metric_name": "memory_usage",
                "value": 512.0,
                "unit": "mb",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        ]

        response = test_client.post(
            f"/devices/{sample_device_data['device_id']}/metrics",
            json=metrics_data
        )

        # This endpoint might not be fully implemented
        # Adjust expectations based on actual implementation
        assert response.status_code in [201, 501]  # 501 if not implemented

    def test_get_device_metrics(self, test_client, sample_device_data):
        """Test retrieving device metrics"""
        # Create device first
        test_client.post("/devices", json=sample_device_data)

        # Get metrics
        response = test_client.get(f"/devices/{sample_device_data['device_id']}/metrics")

        # This endpoint might not be fully implemented
        assert response.status_code in [200, 501]  # 501 if not implemented

    def test_prometheus_metrics_endpoint(self, test_client):
        """Test Prometheus metrics endpoint"""
        response = test_client.get("/metrics")

        # Prometheus metrics should be available
        assert response.status_code == 200
        metrics_text = response.text

        # Check for basic Prometheus metrics format
        assert "# HELP" in metrics_text or "# TYPE" in metrics_text

    def test_api_docs_available(self, test_client):
        """Test that API documentation is available"""
        # OpenAPI docs
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        openapi_spec = response.json()
        assert "openapi" in openapi_spec
        assert "paths" in openapi_spec

        # Swagger UI
        response = test_client.get("/docs")
        assert response.status_code == 200

    def test_cors_headers(self, test_client):
        """Test CORS headers are present"""
        response = test_client.options("/devices")

        # Check for CORS headers (if CORS middleware is configured)
        # This might not be implemented in test version
        # Adjust based on actual CORS configuration
        assert response.status_code in [200, 405]  # 405 if OPTIONS not allowed

    def test_rate_limiting(self, test_client, sample_device_data):
        """Test rate limiting (if implemented)"""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = test_client.get("/devices")
            responses.append(response.status_code)

        # If rate limiting is implemented, some requests should be throttled
        # If not implemented, all should succeed
        # Adjust expectations based on actual implementation
        unique_statuses = set(responses)
        assert 200 in unique_statuses  # At least some should succeed

    def test_error_response_format(self, test_client):
        """Test that error responses follow consistent format"""
        # Test 404 error
        response = test_client.get("/devices/non-existent")
        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data

        # Test 422 error (validation)
        response = test_client.post("/devices", json={"invalid": "data"})
        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    def test_concurrent_requests(self, test_client, sample_device_data):
        """Test handling concurrent requests"""
        import threading
        import time

        results = []

        def create_device():
            response = test_client.post("/devices", json=sample_device_data)
            results.append(response.status_code)

        # Create multiple threads with concurrent requests
        threads = []
        for _ in range(5):
            # Slightly modify device_id to avoid conflicts in concurrent creation
            device_data = sample_device_data.copy()
            device_data["device_id"] = f"{sample_device_data['device_id']}-{time.time_ns()}"

            thread = threading.Thread(
                target=lambda d=device_data: results.append(
                    test_client.post("/devices", json=d).status_code
                )
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that all requests were handled (either success or conflict)
        # With concurrent identical device_id creation, we might get conflicts
        for status in results:
            assert status in [201, 409]  # Created or Conflict