import mysql.connector
from mysql.connector import pooling
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self):
        self.db_config = {
            "pool_name": "mypool",
            "pool_size": 5,
            "host": "localhost",
            "user": "locus",
            "password": "locus",
            "database": "locusSports",
            "autocommit": False
        }
        
        try:
            self.connection_pool = mysql.connector.pooling.MySQLConnectionPool(**self.db_config)
            logger.info("Database connection pool created successfully")
        except mysql.connector.Error as err:
            logger.error(f"Error creating connection pool: {err}")
            raise

    def get_current_epoch_micros(self) -> int:
        """Get current timestamp in microseconds"""
        return int(time.time() * 1_000_000)

    def insert_tracking_data(self, tracking_data: Dict[str, Any]) -> bool:
        """
        Insert player tracking data into the database
        
        Args:
            tracking_data (dict): JSON data received from the sensor
            
        Returns:
            bool: True if insertion was successful, False otherwise
        """
        connection = None
        cursor = None
        try:
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor()
            
            # Extract player ID and verify it exists
            player_id = tracking_data.get('player', {}).get('_id')
            if not player_id:
                logger.error("Missing player ID in tracking data")
                return False
            
            current_time_micros = self.get_current_epoch_micros()
            
            # Update tag assignment first with full tracking data
            self._update_tag_assignment(cursor, player_id, tracking_data['tag_id'], tracking_data)
            
            # Insert tracking data
            tracking_query = """
            INSERT INTO player_tracking_data 
            (player_id, tag_id, timestamp_micros,
             x_position, y_position, 
             accel_x, accel_y, accel_z, 
             gyro_x, gyro_y, gyro_z, 
             battery_life, heart_rate, serial_number, activity_status)
            VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            tracking_values = (
                player_id,
                tracking_data['tag_id'],
                current_time_micros,
                tracking_data['x_position'],
                tracking_data['y_position'],
                tracking_data['accelerometer']['x'],
                tracking_data['accelerometer']['y'],
                tracking_data['accelerometer']['z'],
                tracking_data['gyroscope']['x'],
                tracking_data['gyroscope']['y'],
                tracking_data['gyroscope']['z'],
                tracking_data['battery_life'],
                tracking_data['heart_rate'],
                tracking_data['serial_number'],
                tracking_data['activity_status']
            )
            
            cursor.execute(tracking_query, tracking_values)
            connection.commit()
            
            logger.debug(f"Successfully inserted tracking data for player {player_id}")
            return True
            
        except mysql.connector.Error as err:
            logger.error(f"Database error while inserting tracking data: {err}")
            if connection:
                connection.rollback()
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error while inserting tracking data: {e}")
            if connection:
                connection.rollback()
            return False
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _update_tag_assignment(self, cursor, player_id: str, tag_id: str, tracking_data: Dict[str, Any]) -> None:
        """Update tag assignment record and related player/tag data"""
        try:
            # Extract player info from tracking data
            player_info = tracking_data.get('player', {})
            
            # Update player record with all available fields
            cursor.execute("""
                INSERT INTO players 
                (player_id, name, initials, height, weight, team_id, team_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                initials = VALUES(initials),
                height = VALUES(height),
                weight = VALUES(weight),
                team_id = VALUES(team_id),
                team_name = VALUES(team_name)
            """, (
                player_id,
                player_info.get('name'),
                player_info.get('initials'),
                player_info.get('height'),
                player_info.get('weight'),
                player_info.get('teamid'),
                player_info.get('teamName')
            ))

            # Update tag record
            cursor.execute("""
                INSERT INTO tags 
                (tag_id, serial_number, assigned_player_id, assigned_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                serial_number = VALUES(serial_number),
                assigned_player_id = VALUES(assigned_player_id),
                assigned_at = CURRENT_TIMESTAMP
            """, (
                tag_id,
                tracking_data.get('serial_number'),
                player_id
            ))

            # Update tag assignments
            cursor.execute("""
                UPDATE tag_assignments 
                SET unassigned_at = CURRENT_TIMESTAMP 
                WHERE tag_id = %s AND unassigned_at IS NULL 
                AND player_id != %s
            """, (tag_id, player_id))

            cursor.execute("""
                INSERT INTO tag_assignments (player_id, tag_id)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                unassigned_at = NULL,
                assigned_at = CASE 
                    WHEN unassigned_at IS NOT NULL 
                    THEN CURRENT_TIMESTAMP 
                    ELSE assigned_at 
                END
            """, (player_id, tag_id))

        except mysql.connector.Error as err:
            logger.error(f"Error updating tag assignment: {err}")
            raise

    def get_player_data(self, player_id: str, start_time: int, end_time: int) -> List[Dict[str, Any]]:
        """
        Retrieve player tracking data for a specific time range
        
        Args:
            player_id (str): Player's unique identifier
            start_time (int): Start time in epoch microseconds
            end_time (int): End time in epoch microseconds
            
        Returns:
            list: List of tracking data records
        """
        connection = self.connection_pool.get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT timestamp_micros, x_position, y_position, 
                   accel_x, accel_y, accel_z
            FROM player_tracking_data
            WHERE player_id = %s 
            AND timestamp_micros BETWEEN %s AND %s
            ORDER BY timestamp_micros
        """, (player_id, start_time, end_time))
        
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        return data

    def get_player_latest_data(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Get most recent data for a player"""
        connection = None
        cursor = None
        try:
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            
            query = """
            SELECT * FROM player_tracking_data 
            WHERE player_id = %s 
            ORDER BY timestamp_micros DESC 
            LIMIT 1
            """
            
            cursor.execute(query, (player_id,))
            return cursor.fetchone()
            
        except mysql.connector.Error as err:
            logger.error(f"Error retrieving latest player data: {err}")
            return None
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        """Clean up data older than specified days"""
        connection = None
        cursor = None
        try:
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor()
            
            cutoff_time = int((time.time() - (days_to_keep * 86400)) * 1_000_000)
            
            # Clean up old tracking data
            cursor.execute("""
                DELETE FROM player_tracking_data 
                WHERE timestamp_micros < %s
            """, (cutoff_time,))
            
            # Clean up old tag assignments
            cursor.execute("""
                DELETE FROM tag_assignments 
                WHERE unassigned_at < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL %s DAY)
            """, (days_to_keep,))
            
            connection.commit()
            return True
            
        except mysql.connector.Error as err:
            logger.error(f"Error cleaning up old data: {err}")
            if connection:
                connection.rollback()
            return False
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()