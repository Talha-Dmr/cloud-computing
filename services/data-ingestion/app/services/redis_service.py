import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis
import structlog

from ..config import settings

logger = structlog.get_logger()


class RedisService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.is_connected = False

    async def connect(self):
        """
        Connect to Redis
        """
        try:
            self.redis_client = redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )

            # Test connection
            await self.redis_client.ping()
            self.is_connected = True
            logger.info("Connected to Redis")

        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            self.is_connected = False
            raise

    async def disconnect(self):
        """
        Disconnect from Redis
        """
        if self.redis_client:
            await self.redis_client.close()
            self.is_connected = False
            logger.info("Disconnected from Redis")

    async def cache_device_info(
        self, device_id: str, device_info: Dict[str, Any], ttl: int = 300
    ):
        """
        Cache device information
        """
        if not self.is_connected:
            return

        try:
            key = f"device:{device_id}:info"
            await self.redis_client.setex(key, ttl, json.dumps(device_info))
            logger.debug("Device info cached", device_id=device_id, ttl=ttl)

        except Exception as e:
            logger.error(
                "Failed to cache device info", device_id=device_id, error=str(e)
            )

    async def get_cached_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached device information
        """
        if not self.is_connected:
            return None

        try:
            key = f"device:{device_id}:info"
            cached_data = await self.redis_client.get(key)

            if cached_data:
                return json.loads(cached_data)

            return None

        except Exception as e:
            logger.error(
                "Failed to get cached device info", device_id=device_id, error=str(e)
            )
            return None

    async def update_device_last_seen(self, device_id: str):
        """
        Update device last seen timestamp
        """
        if not self.is_connected:
            return

        try:
            key = f"device:{device_id}:last_seen"
            await self.redis_client.setex(
                key, 86400, datetime.utcnow().isoformat()  # 24 hours
            )

            # Also update active devices set
            await self.redis_client.sadd("devices:active", device_id)
            await self.redis_client.expire("devices:active", 300)  # 5 minutes

        except Exception as e:
            logger.error(
                "Failed to update device last seen", device_id=device_id, error=str(e)
            )

    async def set_device_health(self, device_id: str, health_data: Dict[str, Any]):
        """
        Set device health status
        """
        if not self.is_connected:
            return

        try:
            key = f"device:{device_id}:health"
            await self.redis_client.setex(key, 3600, json.dumps(health_data))  # 1 hour

        except Exception as e:
            logger.error(
                "Failed to set device health", device_id=device_id, error=str(e)
            )

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device status information
        """
        if not self.is_connected:
            return None

        try:
            # Get last seen
            last_seen_key = f"device:{device_id}:last_seen"
            last_seen = await self.redis_client.get(last_seen_key)

            # Get health
            health_key = f"device:{device_id}:health"
            health_data = await self.redis_client.get(health_key)

            # Determine if device is online
            is_online = False
            if last_seen:
                last_seen_time = datetime.fromisoformat(last_seen)
                is_online = (datetime.utcnow() - last_seen_time) < timedelta(minutes=5)

            status = {
                "device_id": device_id,
                "last_seen": last_seen,
                "is_online": is_online,
                "health": json.loads(health_data) if health_data else None,
            }

            return status

        except Exception as e:
            logger.error(
                "Failed to get device status", device_id=device_id, error=str(e)
            )
            return None

    async def increment_device_data_points(self, device_id: str, count: int = 1):
        """
        Increment data points counter for a device
        """
        if not self.is_connected:
            return

        try:
            # Daily counter
            today = datetime.utcnow().strftime("%Y-%m-%d")
            daily_key = f"device:{device_id}:data_points:{today}"
            await self.redis_client.incrby(daily_key, count)
            await self.redis_client.expire(daily_key, 86400 * 7)  # Keep for 7 days

            # Total counter
            total_key = f"device:{device_id}:data_points:total"
            await self.redis_client.incrby(total_key, count)

            # Global counters
            await self.redis_client.incrby("stats:data_points:today", count)
            await self.redis_client.incrby("stats:data_points:total", count)

        except Exception as e:
            logger.error(
                "Failed to increment device data points",
                device_id=device_id,
                error=str(e),
            )

    async def get_active_devices_count(self) -> int:
        """
        Get count of currently active devices
        """
        if not self.is_connected:
            return 0

        try:
            return await self.redis_client.scard("devices:active")
        except Exception as e:
            logger.error("Failed to get active devices count", error=str(e))
            return 0

    async def get_total_devices_count(self) -> int:
        """
        Get total number of devices
        """
        if not self.is_connected:
            return 0

        try:
            # Count all device keys
            pattern = "device:*:info"
            keys = await self.redis_client.keys(pattern)
            return len(keys)
        except Exception as e:
            logger.error("Failed to get total devices count", error=str(e))
            return 0

    async def get_data_points_today(self) -> int:
        """
        Get total data points received today
        """
        if not self.is_connected:
            return 0

        try:
            count = await self.redis_client.get("stats:data_points:today")
            return int(count) if count else 0
        except Exception as e:
            logger.error("Failed to get today's data points", error=str(e))
            return 0

    async def get_total_data_points(self) -> int:
        """
        Get total data points received
        """
        if not self.is_connected:
            return 0

        try:
            count = await self.redis_client.get("stats:data_points:total")
            return int(count) if count else 0
        except Exception as e:
            logger.error("Failed to get total data points", error=str(e))
            return 0

    async def cleanup_expired_data(self):
        """
        Clean up expired data (should be run periodically)
        """
        if not self.is_connected:
            return

        try:
            # Clean up old daily counters
            cutoff_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            pattern = "device:*:data_points:*"

            keys = await self.redis_client.keys(pattern)
            deleted = 0

            for key in keys:
                parts = key.split(":")
                if len(parts) >= 4 and parts[3] < cutoff_date:
                    await self.redis_client.delete(key)
                    deleted += 1

            logger.info("Cleaned up expired data", keys_deleted=deleted)

        except Exception as e:
            logger.error("Failed to cleanup expired data", error=str(e))
