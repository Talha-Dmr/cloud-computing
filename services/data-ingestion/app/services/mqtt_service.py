import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt
import structlog

from ..config import settings
from .ingestion_service import DataIngestionService

logger = structlog.get_logger()


class MQTTService:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.ingestion_service: Optional[DataIngestionService] = None
        self.is_connected = False
        self.message_handlers: Dict[str, Callable] = {}

    async def start(self):
        """
        Start MQTT client and connect to broker
        """
        try:
            # Create MQTT client
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            # Set username/password if provided
            if settings.mqtt_username and settings.mqtt_password:
                self.client.username_pw_set(
                    settings.mqtt_username, settings.mqtt_password
                )

            # Connect to broker
            self.client.connect(settings.mqtt_host, settings.mqtt_port, 60)

            # Start the network loop in a separate thread
            self.client.loop_start()

            # Wait for connection
            for _ in range(10):  # Wait up to 5 seconds
                if self.is_connected:
                    break
                await asyncio.sleep(0.5)

            if not self.is_connected:
                raise Exception("Failed to connect to MQTT broker")

            logger.info(
                "MQTT service started", host=settings.mqtt_host, port=settings.mqtt_port
            )

        except Exception as e:
            logger.error("Failed to start MQTT service", error=str(e))
            raise

    async def stop(self):
        """
        Stop MQTT client
        """
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            logger.info("MQTT service stopped")

    def _on_connect(self, client, userdata, flags, rc):
        """
        MQTT connect callback
        """
        if rc == 0:
            self.is_connected = True
            logger.info("Connected to MQTT broker")

            # Subscribe to default topics
            self._subscribe_to_default_topics()

        else:
            self.is_connected = False
            logger.error("Failed to connect to MQTT broker", return_code=rc)

    def _on_disconnect(self, client, userdata, rc):
        """
        MQTT disconnect callback
        """
        self.is_connected = False
        logger.warning("Disconnected from MQTT broker", return_code=rc)

    def _on_message(self, client, userdata, msg):
        """
        MQTT message callback
        """
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8")

            logger.debug(
                "Received MQTT message", topic=topic, payload_length=len(payload)
            )

            # Parse topic to extract device information
            topic_parts = topic.split("/")
            device_id = None

            # Expected topic format: iot/{device_id}/data or iot/{device_id}/health
            if len(topic_parts) >= 3 and topic_parts[0] == "iot":
                device_id = topic_parts[1]
                message_type = topic_parts[2]

                # Handle different message types
                asyncio.create_task(
                    self._handle_mqtt_message(device_id, message_type, payload)
                )

            # Call custom handler if registered
            if topic in self.message_handlers:
                asyncio.create_task(self.message_handlers[topic](topic, payload))

        except Exception as e:
            logger.error(
                "Failed to process MQTT message", topic=msg.topic, error=str(e)
            )

    def _subscribe_to_default_topics(self):
        """
        Subscribe to default MQTT topics
        """
        default_topics = [
            "iot/+/data",  # Device data
            "iot/+/health",  # Device health
            "iot/+/status",  # Device status
            "iot/+/alert",  # Device alerts
        ]

        for topic in default_topics:
            self.client.subscribe(topic)
            logger.debug("Subscribed to MQTT topic", topic=topic)

    async def _handle_mqtt_message(
        self, device_id: str, message_type: str, payload: str
    ):
        """
        Handle incoming MQTT message based on type
        """
        try:
            # Parse JSON payload
            data = json.loads(payload)

            if message_type == "data":
                await self._handle_data_message(device_id, data)
            elif message_type == "health":
                await self._handle_health_message(device_id, data)
            elif message_type == "status":
                await self._handle_status_message(device_id, data)
            elif message_type == "alert":
                await self._handle_alert_message(device_id, data)
            else:
                logger.warning(
                    "Unknown MQTT message type",
                    device_id=device_id,
                    message_type=message_type,
                )

        except json.JSONDecodeError:
            logger.error(
                "Invalid JSON in MQTT message",
                device_id=device_id,
                message_type=message_type,
                payload=payload[:100],
            )
        except Exception as e:
            logger.error(
                "Failed to handle MQTT message",
                device_id=device_id,
                message_type=message_type,
                error=str(e),
            )

    async def _handle_data_message(self, device_id: str, data: Dict[str, Any]):
        """
        Handle device data message
        """
        if not self.ingestion_service:
            logger.warning(
                "Ingestion service not available for MQTT data message",
                device_id=device_id,
            )
            return

        try:
            # Convert to ingestion request format
            ingestion_request = {
                "device_id": device_id,
                "data": data.get("data", []),
                "batch_id": data.get("batch_id"),
                "location": data.get("location"),
                "firmware_version": data.get("firmware_version"),
                "battery_level": data.get("battery_level"),
            }

            # Get device info (simplified - in real implementation,
            # you'd authenticate the device)
            device_info = {"device_id": device_id, "device_type": "sensor"}

            # Process data
            await self.ingestion_service.process_data(ingestion_request, device_info)

            logger.info(
                "MQTT data message processed",
                device_id=device_id,
                data_points=len(ingestion_request.get("data", [])),
            )

        except Exception as e:
            logger.error(
                "Failed to process MQTT data message", device_id=device_id, error=str(e)
            )

    async def _handle_health_message(self, device_id: str, data: Dict[str, Any]):
        """
        Handle device health message
        """
        if not self.ingestion_service:
            return

        try:
            is_healthy = data.get("is_healthy", True)
            message = data.get("message")

            await self.ingestion_service.update_device_health(
                device_id, is_healthy, message
            )

            logger.info(
                "MQTT health message processed",
                device_id=device_id,
                is_healthy=is_healthy,
            )

        except Exception as e:
            logger.error(
                "Failed to process MQTT health message",
                device_id=device_id,
                error=str(e),
            )

    async def _handle_status_message(self, device_id: str, data: Dict[str, Any]):
        """
        Handle device status message
        """
        # Similar to health but might include more detailed status
        await self._handle_health_message(device_id, data)

    async def _handle_alert_message(self, device_id: str, data: Dict[str, Any]):
        """
        Handle device alert message
        """
        try:
            # Forward alert to Kafka for processing by Alert Engine
            from .kafka_producer import KafkaProducerService

            # Note: In a real implementation, you'd have proper dependency injection
            # This is simplified for demonstration
            alert_data = {
                "device_id": device_id,
                "alert": data,
                "source": "mqtt",
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info(
                "MQTT alert message received",
                device_id=device_id,
                alert_type=data.get("type", "unknown"),
            )

        except Exception as e:
            logger.error(
                "Failed to process MQTT alert message",
                device_id=device_id,
                error=str(e),
            )

    def subscribe(self, topic: str, handler: Callable):
        """
        Subscribe to a custom MQTT topic with handler
        """
        if self.client:
            self.client.subscribe(topic)
            self.message_handlers[topic] = handler
            logger.info("Subscribed to custom MQTT topic", topic=topic)

    def publish(self, topic: str, payload: Dict[str, Any]):
        """
        Publish message to MQTT topic
        """
        if not self.client or not self.is_connected:
            logger.error("Cannot publish - MQTT not connected", topic=topic)
            return False

        try:
            payload_str = json.dumps(payload)
            result = self.client.publish(topic, payload_str)

            if result.rc == 0:
                logger.debug(
                    "MQTT message published", topic=topic, message_id=result.mid
                )
                return True
            else:
                logger.error(
                    "Failed to publish MQTT message", topic=topic, return_code=result.rc
                )
                return False

        except Exception as e:
            logger.error("Error publishing MQTT message", topic=topic, error=str(e))
            return False

    def set_ingestion_service(self, ingestion_service: DataIngestionService):
        """
        Set the ingestion service for handling messages
        """
        self.ingestion_service = ingestion_service
