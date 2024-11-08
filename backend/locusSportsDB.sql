CREATE DATABASE IF NOT EXISTS locusSports;
USE locusSports;

-- Players Table
-- Stores basic player information
CREATE TABLE players (
    player_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(100),
    initials VARCHAR(10),
    height INT,
    weight INT,
    team_id VARCHAR(255),
    team_name VARCHAR(100)
);

-- Tags Table
-- Stores information about physical tracking tags
CREATE TABLE tags (
    tag_id VARCHAR(50) PRIMARY KEY,
    serial_number INT,
    assigned_player_id VARCHAR(255),
    assigned_at DATETIME,
    unassigned_at DATETIME,
    FOREIGN KEY (assigned_player_id) REFERENCES players(player_id)
);

-- Player Tracking Data Table
-- Stores real-time tracking data from sensors
CREATE TABLE player_tracking_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    player_id VARCHAR(255),
    tag_id VARCHAR(50),
    timestamp_micros BIGINT,
    x_position FLOAT,
    y_position FLOAT,
    accel_x FLOAT,
    accel_y FLOAT,
    accel_z FLOAT,
    gyro_x FLOAT,
    gyro_y FLOAT,
    gyro_z FLOAT,
    battery_life INT,
    heart_rate INT,
    serial_number INT,
    activity_status INT,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id)
);

-- Tag Assignments Table
-- Tracks the history of tag assignments to players
CREATE TABLE tag_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    player_id VARCHAR(255),
    tag_id VARCHAR(50),
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    unassigned_at DATETIME NULL,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id)
);

ALTER TABLE players 
MODIFY name VARCHAR(100) NULL,
MODIFY initials VARCHAR(10) NULL,
MODIFY height INT NULL,
MODIFY weight INT NULL,
MODIFY team_id VARCHAR(255) NULL,
MODIFY team_name VARCHAR(100) NULL;

ALTER TABLE tags 
MODIFY serial_number INT NULL,
MODIFY assigned_player_id VARCHAR(255) NULL,
MODIFY assigned_at DATETIME NULL,
MODIFY unassigned_at DATETIME