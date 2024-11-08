import asyncio
import logging
import struct
import json
import aiohttp
import logging
from database_handler import DatabaseHandler
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
import paho.mqtt.client as mqtt3
import traceback
from typing import Optional, Dict, Any


# Initialize the database handler
db_handler = DatabaseHandler()

logger = logging.getLogger(__name__)

# MQTT broker configuration
broker_address = "localhost"
broker_port = 1883
base_topic = "leaps/1234/node/uplink/ble_location"

# API configuration
API_BASE_URL = "http://localhost:5000/api/tag/tagInfo"
API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiNjZjZWZiYWY4NmIyNjdlZTAwZjU0NDg3In0sImlhdCI6MTcyODEzMzAzNSwiZXhwIjoxNzM1OTA5MDM1fQ.NaUH3PaB3BWlayNC8AsodGR8SNGgX2kme_A47vf5XcA"


# Create a MQTT client instance
mqtt_client = mqtt3.Client()

# Connect to the MQTT broker
mqtt_client.connect(broker_address, broker_port)

async def fetch_player_info(tag_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch player information from the API using tag ID.
    
    Args:
        tag_id (str): The tag ID to look up
        
    Returns:
        Optional[Dict[str, Any]]: Player information if available, None if no player is linked or tag not found
    """
    try:
        headers = {
            'Authorization': API_TOKEN,
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}/{tag_id}"
            async with session.get(url, headers=headers) as response:
                logger.debug(f"API request to {url} returned status: {response.status}")
                
                if response.status == 500:
                    logger.error("Server error occurred. Token might be invalid.")
                    return None
                
                if response.status == 404:
                    logger.warning(f"Tag {tag_id} not found in database")
                    return None
                
                if response.content_type == 'application/json':
                    response_data = await response.json()
                    if response_data.get("status") == "success":
                        return response_data.get("data", {}).get("player")
                    logger.error(f"API request failed: {response_data}")
                    return None
                
                logger.error(f"Unexpected response content type: {response.content_type}")
                return None
                
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching player info: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching player info: {e}")
        logger.error(traceback.format_exc())
        return None


def publish_data(tag_id: str, json_data: str):
    """
    Publish JSON data to the MQTT topic with the tag ID.
    
    Args:
        tag_id (str): The tag ID for the MQTT topic
        json_data (str): JSON data to publish
    """
    topic = f"{base_topic}/{tag_id}"
    mqtt_client.publish(topic, json_data)

async def notification_handler(tag_id: str, characteristic: BleakGATTCharacteristic, data: bytearray):
    """
    Notification handler for processing received data.
    
    Args:
        tag_id (str): The tag ID from the MQTT topic
        characteristic (BleakGATTCharacteristic): The BLE characteristic
        data (bytearray): The received data
    """
    try:
        # Print the hexadecimal representation of the received data
        hex_data = ":".join("{:02x}".format(byte) for byte in data)
        logger.info("Received data (hex): %s", hex_data)

        if len(data) != 36:
            logger.error(f"Invalid data length: {len(data)} bytes (expected 36)")
            return

        # Unpack data using struct
        try:
            (x_position, y_position, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z,
             battery_life, hr, serial_number, activity_status) = struct.unpack(
                "<8f4B", data)  # 8 floats followed by 4 unsigned chars
        except struct.error as e:
            logger.error(f"Error unpacking data structure: {e}")
            return

        # Fetch player information
        player_info = await fetch_player_info(tag_id)
        if not player_info:
            logger.warning(f"No player info found for tag {tag_id}")
            return

        # Prepare decoded data
        decoded_data = {
            "x_position": x_position,
            "y_position": y_position,
            "accelerometer": {
                "x": accel_x,
                "y": accel_y,
                "z": accel_z
            },
            "gyroscope": {
                "x": gyro_x,
                "y": gyro_y,
                "z": gyro_z
            },
            "battery_life": battery_life,
            "heart_rate": hr,
            "serial_number": serial_number,
            "activity_status": activity_status,
            "tag_id": tag_id,
            "player": player_info
        }

        # Insert into database
        if not db_handler.insert_tracking_data(decoded_data):
            logger.error(f"Failed to insert tracking data for tag {tag_id}")
            return

        # Publish to MQTT
        json_data = json.dumps(decoded_data)
        publish_data(tag_id, json_data)

        # Log the received data and success
        logger.info("Received data (JSON): %s", json_data)
        logger.debug(f"Successfully processed data for tag {tag_id}")

    except Exception as e:
        logger.error(f"Error processing notification: {e}")
        logger.error(traceback.format_exc())

mqtt_client.loop_start()

async def connect_and_subscribe(device_address: str, characteristic_uuid: str, tag_id: str):
    """
    Connect to BLE device and subscribe to notifications.
    
    Args:
        device_address (str): The BLE device address
        characteristic_uuid (str): The characteristic UUID to subscribe to
        tag_id (str): The tag ID for the MQTT topic
    """
    async def handle_disconnected(client):
        logger.info("Disconnected from device %s", device_address)
        if client.is_connected:
            await client.stop_notify(characteristic_uuid)
            await client.disconnect()
        await asyncio.sleep(5)  # Wait before attempting to reconnect
        await connect_and_subscribe(device_address, characteristic_uuid, tag_id)  # Attempt reconnection

    def handle_disconnected_wrapper(client):
        asyncio.create_task(handle_disconnected(client))

    client = BleakClient(device_address, mtu=40, disconnected_callback=handle_disconnected_wrapper)
    
    try:
        logger.info("Connecting to device %s...", device_address)
        await client.connect()
        
        logger.info("Connected to device %s", device_address)
        
        # Create a notification handler that includes the tag ID
        handler = lambda c, d: asyncio.create_task(notification_handler(tag_id, c, d))
        await client.start_notify(characteristic_uuid, handler)
        
        # Wait indefinitely to keep the notifications on
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error("Error connecting to device %s: %s", device_address, e)
        logger.info("Attempting to reconnect to device %s in 5 seconds...", device_address)
        await asyncio.sleep(5)  # Wait before attempting to reconnect
        await connect_and_subscribe(device_address, characteristic_uuid, tag_id)  # Attempt reconnection

async def main():
    #DE:C5:A6:A5:1A:D8
    device_address = "de:c5:a6:a5:1a:d8"
    characteristic_uuid = "ef47b05a-5571-4688-8aba-9c6b51463208"
    tag_id = "0f1c"  # The tag ID for the MQTT topic
    await connect_and_subscribe(device_address, characteristic_uuid, tag_id)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s")
    asyncio.run(main())