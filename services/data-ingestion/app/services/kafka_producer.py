import asyncio
import json
from typing import Any
from typing import Dict
from typing import Optional

import structlog
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from ..config import settings

logger = structlog.get_logger()


class KafkaProducerService:
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.is_connected = False

    async def start(self):
        """
        Initialize and start the Kafka producer
        """
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                linger_ms=10,
                compression_type="gzip",
            )

            await self.producer.start()
            self.is_connected = True
            logger.info("Kafka producer started successfully")

        except Exception as e:
            logger.error("Failed to start Kafka producer", error=str(e))
            self.is_connected = False
            raise

    async def stop(self):
        """
        Stop the Kafka producer
        """
        if self.producer:
            await self.producer.stop()
            self.is_connected = False
            logger.info("Kafka producer stopped")

    async def send_message(
        self,
        topic: str,
        value: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Send a message to Kafka topic
        """
        if not self.is_connected or not self.producer:
            logger.error("Kafka producer not connected")
            return False

        try:
            # Convert headers to list of tuples if provided
            kafka_headers = []
            if headers:
                kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

            # Send message
            await self.producer.send_and_wait(
                topic=topic, value=value, key=key, headers=kafka_headers
            )

            logger.debug(
                "Message sent to Kafka",
                topic=topic,
                key=key,
                value_keys=list(value.keys()),
            )

            return True

        except KafkaError as e:
            logger.error(
                "Failed to send message to Kafka", topic=topic, key=key, error=str(e)
            )
            return False

        except Exception as e:
            logger.error(
                "Unexpected error sending to Kafka", topic=topic, key=key, error=str(e)
            )
            return False

    async def send_batch(self, messages: list[Dict[str, Any]]) -> int:
        """
        Send multiple messages in a batch
        """
        if not self.is_connected or not self.producer:
            logger.error("Kafka producer not connected")
            return 0

        successful = 0
        try:
            # Create batch
            batch = self.producer.create_batch()

            for msg in messages:
                value_json = json.dumps(msg.get("value", {}), default=str).encode(
                    "utf-8"
                )
                key = msg.get("key", "").encode("utf-8") if msg.get("key") else None

                # Add to batch
                batch.append(key=key, value=value_json, timestamp=None, headers=[])
                successful += 1

            # Send batch
            partitions = await self.producer.send_batch(
                batch=batch, topic=messages[0].get("topic"), partition=-1
            )

            logger.info(
                "Batch sent to Kafka",
                topic=messages[0].get("topic"),
                message_count=successful,
            )

            return successful

        except Exception as e:
            logger.error(
                "Failed to send batch to Kafka",
                error=str(e),
                attempted_count=len(messages),
            )
            return 0

    async def get_queue_size(self) -> int:
        """
        Get approximate number of messages in producer queue
        """
        if not self.producer:
            return 0

        # This is a simplified implementation
        # In a real scenario, you might track this more accurately
        return 0

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Kafka producer health
        """
        health_status = {
            "status": "unhealthy",
            "connected": self.is_connected,
            "error": None,
        }

        if not self.is_connected:
            health_status["error"] = "Producer not connected"
            return health_status

        try:
            # Try to send a health check message
            test_message = {
                "type": "health_check",
                "timestamp": str(asyncio.get_event_loop().time()),
                "service": "data-ingestion",
            }

            success = await self.send_message(
                topic="health-checks", value=test_message, key="data-ingestion-health"
            )

            if success:
                health_status["status"] = "healthy"

        except Exception as e:
            health_status["error"] = str(e)
            logger.error("Kafka health check failed", error=str(e))

        return health_status
