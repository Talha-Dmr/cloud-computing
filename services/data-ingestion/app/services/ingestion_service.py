import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from ..config import settings
from ..schemas.ingestion import DataIngestionRequest, DeviceStatus, IngestionStats
from .kafka_producer import KafkaProducerService
from .redis_service import RedisService

logger = structlog.get_logger()


class DataIngestionService:
    def __init__(
        self, kafka_producer: KafkaProducerService, redis_service: RedisService
    ):
        self.kafka_producer = kafka_producer
        self.redis_service = redis_service
        self.start_time = datetime.utcnow()

    async def authenticate_device(
        self, token: str, device_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate device using JWT token
        """
        try:
            # In a real implementation, you would verify the JWT token
            # with the Device Registry service
            device_info = await self._get_device_info(device_id)

            if not device_info:
                logger.warning("Device not found", device_id=device_id)
                return None

            # Update last seen timestamp
            await self.redis_service.update_device_last_seen(device_id)

            return device_info

        except Exception as e:
            logger.error("Authentication failed", device_id=device_id, error=str(e))
            return None

    async def process_data(self, data: Dict[str, Any], device_info: Dict[str, Any]):
        """
        Process incoming IoT data and send to Kafka
        """
        try:
            device_id = data["device_id"]
            data_points = data["data"]

            # Enrich data with device information
            enriched_data = {
                "device_id": device_id,
                "device_info": device_info,
                "data": data_points,
                "received_at": datetime.utcnow().isoformat(),
                "batch_id": data.get("batch_id"),
                "location": data.get("location"),
                "firmware_version": data.get("firmware_version"),
                "battery_level": data.get("battery_level"),
            }

            # Send to Kafka for processing
            await self.kafka_producer.send_message(
                topic=settings.kafka_topic_data, key=device_id, value=enriched_data
            )

            # Update device statistics in Redis
            await self.redis_service.increment_device_data_points(
                device_id, len(data_points)
            )

            # Check for alerts (simplified - in real implementation,
            # this would be handled by the Alert Engine service)
            await self._check_alerts(device_id, data_points, device_info)

            logger.info(
                "Data processed successfully",
                device_id=device_id,
                data_points_count=len(data_points),
            )

        except Exception as e:
            logger.error(
                "Failed to process data", device_id=data.get("device_id"), error=str(e)
            )
            # Send to error topic for retry
            await self.kafka_producer.send_message(
                topic=settings.kafka_topic_errors,
                key=data.get("device_id", "unknown"),
                value={
                    "error": str(e),
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def update_device_health(
        self, device_id: str, is_healthy: bool, message: Optional[str] = None
    ):
        """
        Update device health status
        """
        try:
            health_data = {
                "device_id": device_id,
                "is_healthy": is_healthy,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Update Redis
            await self.redis_service.set_device_health(device_id, health_data)

            # Send to Kafka for alert processing
            await self.kafka_producer.send_message(
                topic=settings.kafka_topic_health, key=device_id, value=health_data
            )

            logger.info(
                "Device health updated", device_id=device_id, is_healthy=is_healthy
            )

        except Exception as e:
            logger.error(
                "Failed to update device health", device_id=device_id, error=str(e)
            )

    async def get_stats(self) -> IngestionStats:
        """
        Get service statistics
        """
        try:
            total_devices = await self.redis_service.get_total_devices_count()
            active_devices = await self.redis_service.get_active_devices_count()
            data_points_today = await self.redis_service.get_data_points_today()
            data_points_total = await self.redis_service.get_total_data_points()
            messages_in_queue = await self.kafka_producer.get_queue_size()

            uptime = datetime.utcnow() - self.start_time
            uptime_str = str(uptime).split(".")[0]  # Remove microseconds

            return IngestionStats(
                total_devices=total_devices,
                active_devices=active_devices,
                data_points_today=data_points_today,
                data_points_total=data_points_total,
                messages_in_queue=messages_in_queue,
                average_processing_time=0.1,  # Placeholder - would track actual times
                uptime=uptime_str,
            )

        except Exception as e:
            logger.error("Failed to get stats", error=str(e))
            raise

    async def _get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device information from cache or Device Registry
        """
        # Try to get from Redis cache first
        cached_info = await self.redis_service.get_cached_device_info(device_id)

        if cached_info:
            return cached_info

        # If not in cache, fetch from Device Registry service
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://device-registry:8001/devices/{device_id}",
                    headers={"Authorization": f"Bearer {settings.service_token}"},
                )

                if response.status_code == 200:
                    device_info = response.json()
                    # Cache for 5 minutes
                    await self.redis_service.cache_device_info(
                        device_id, device_info, ttl=300
                    )
                    return device_info

        except Exception as e:
            logger.error(
                "Failed to fetch device info", device_id=device_id, error=str(e)
            )

        return None

    async def _check_alerts(
        self,
        device_id: str,
        data_points: List[Dict[str, Any]],
        device_info: Dict[str, Any],
    ):
        """
        Check if any data points trigger alerts
        """
        try:
            alerts = []

            for data_point in data_points:
                # Temperature alerts
                if data_point.get("data_type") == "temperature":
                    temp = float(data_point.get("value", 0))
                    if temp > 50:
                        alerts.append(
                            {
                                "device_id": device_id,
                                "metric": "temperature",
                                "value": temp,
                                "threshold": 50,
                                "severity": "high",
                                "message": f"High temperature detected: {temp}°C",
                            }
                        )
                    elif temp < 0:
                        alerts.append(
                            {
                                "device_id": device_id,
                                "metric": "temperature",
                                "value": temp,
                                "threshold": 0,
                                "severity": "medium",
                                "message": f"Low temperature detected: {temp}°C",
                            }
                        )

                # Battery level alerts
                if data_point.get("metric_name") == "battery_level":
                    battery = float(data_point.get("value", 100))
                    if battery < 10:
                        alerts.append(
                            {
                                "device_id": device_id,
                                "metric": "battery_level",
                                "value": battery,
                                "threshold": 10,
                                "severity": "high",
                                "message": f"Low battery: {battery}%",
                            }
                        )

            # Send alerts to Kafka if any
            if alerts:
                for alert in alerts:
                    await self.kafka_producer.send_message(
                        topic=settings.kafka_topic_alerts,
                        key=device_id,
                        value={
                            **alert,
                            "timestamp": datetime.utcnow().isoformat(),
                            "device_info": device_info,
                        },
                    )

        except Exception as e:
            logger.error("Failed to check alerts", device_id=device_id, error=str(e))
