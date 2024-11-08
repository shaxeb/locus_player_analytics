from flask import Flask, jsonify, request
from flask_cors import CORS
from database_handler import DatabaseHandler
import numpy as np
from scipy.signal import find_peaks
import pandas as pd
import math

app = Flask(__name__)
CORS(app)

db = DatabaseHandler()

def calculate_speed_and_displacement(x_positions, y_positions, z_positions, timestamps):
    """
    Calculate speed and displacement using trapezoidal integration method
    adapted from accelcat.py for post-processing data
    """
    dt = np.diff(timestamps) / 1_000_000  # Convert microseconds to seconds
    
    # Initialize arrays
    speeds = np.zeros(len(timestamps))
    displacements = np.zeros(len(timestamps))
    
    # Calculate velocities using trapezoidal integration
    dx = np.diff(x_positions)
    dy = np.diff(y_positions)
    dz = np.diff(z_positions)
    
    # Calculate 3D velocities
    vx = dx / dt
    vy = dy / dt
    vz = dz / dt
    
    # Calculate speed magnitude (including all three dimensions)
    speeds[1:] = np.sqrt(vx**2 + vy**2 + vz**2)
    
    # Calculate displacements using trapezoidal integration of speeds
    for i in range(1, len(timestamps)):
        time_interval = (timestamps[i] - timestamps[i-1]) / 1_000_000  # Convert to seconds
        displacements[i] = displacements[i-1] + (speeds[i] + speeds[i-1]) * time_interval / 2
    
    return speeds, displacements

def calculate_acceleration(ax, ay, az):
    """Calculate acceleration magnitude with gravity compensation"""
    acc_magnitude = np.sqrt(ax**2 + ay**2 + az**2) - 9.81
    return acc_magnitude

def detect_steps(acc_magnitude, threshold):
    step_counter = 0
    step_b_ts = -1
    step_e_ts = -1
    prev_acc = -1

    for ts, current_acc in enumerate(acc_magnitude):
        if prev_acc != -1 and current_acc > threshold:
            if prev_acc < threshold:
                step_b_ts = ts  # Step begins
        elif prev_acc >= threshold and current_acc <= threshold:
            step_e_ts = ts  # Step ends
            if step_b_ts != -1 and step_e_ts > step_b_ts:
                step_counter += 1
        prev_acc = current_acc

    return step_counter

def detect_jumps(acc_buffer, jump_threshold):
    # Low-pass filter
    alpha = 0.2
    filtered_acc = np.zeros_like(acc_buffer)
    filtered_acc[0] = acc_buffer[0]
    for i in range(1, len(acc_buffer)):
        filtered_acc[i] = alpha * acc_buffer[i] + (1 - alpha) * filtered_acc[i-1]
    
    # Peak detection
    jump_count = 0
    min_distance = 5
    last_jump_time = -1

    for i in range(1, len(filtered_acc) - 1):
        if (filtered_acc[i] > filtered_acc[i-1] and 
            filtered_acc[i] > filtered_acc[i+1] and 
            filtered_acc[i] > jump_threshold):
            if (i == 1 or i - 1 >= min_distance):
                jump_count += 1
                last_jump_time = i

    return jump_count

@app.route('/api/player-analytics', methods=['GET'])
def get_player_analytics():
    player_id = request.args.get('player_id')
    start_time = int(request.args.get('start_time'))
    end_time = int(request.args.get('end_time'))
    
    # Get tracking data from database
    tracking_data = db.get_player_data(player_id, start_time, end_time)
    
    if not tracking_data:
        return jsonify({'error': 'No data found'}), 404
    
    # Prepare data for processing
    timestamps = np.array([d.get('timestamp_micros', 0) for d in tracking_data])
    x_positions = np.array([d.get('x_position', 0) for d in tracking_data])
    y_positions = np.array([d.get('y_position', 0) for d in tracking_data])
    z_positions = np.array([d.get('z_position', 0) for d in tracking_data])
    
    ax = np.array([d.get('accel_x', 0) for d in tracking_data])
    ay = np.array([d.get('accel_y', 0) for d in tracking_data])
    az = np.array([d.get('accel_z', 0) for d in tracking_data])
    
    # Calculate metrics using enhanced methods
    speeds, displacements = calculate_speed_and_displacement(
        x_positions, y_positions, z_positions, timestamps
    )
    acc_magnitude = calculate_acceleration(ax, ay, az)
    step_count = detect_steps(acc_magnitude, threshold=2.0)
    jump_count = detect_jumps(acc_magnitude, jump_threshold=4.0)
    
    # Calculate statistics
    avg_speed = np.mean(speeds)
    max_speed = np.max(speeds)
    total_displacement = displacements[-1]
    
    return jsonify({
        'speeds': {
            'data': speeds.tolist(),
            'timestamps': timestamps.tolist(),
            'average': float(avg_speed),
            'max': float(max_speed)
        },
        'displacement': {
            'data': displacements.tolist(),
            'timestamps': timestamps.tolist(),
            'total': float(total_displacement)
        },
        'steps': {
            'count': step_count,
            'timestamps': timestamps.tolist(),
            'magnitudes': acc_magnitude.tolist()
        },
        'jumps': {
            'count': jump_count,
            'timestamps': timestamps.tolist(),
            'magnitudes': acc_magnitude.tolist()
        },
        'acceleration_magnitude': {
            'data': acc_magnitude.tolist(),
            'timestamps': timestamps.tolist()
        }
    })

@app.route('/api/players', methods=['GET'])
def get_players():
    connection = db.connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("SELECT player_id, name FROM players WHERE name IS NOT NULL")
    players = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return jsonify(players)

@app.route('/api/player-time-range', methods=['GET'])
def get_player_time_range():
    connection = db.connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT player_id, MIN(timestamp_micros) AS start_time, MAX(timestamp_micros) AS end_time
        FROM player_tracking_data
        GROUP BY player_id
    """)
    time_ranges = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return jsonify(time_ranges)

if __name__ == '__main__':
    app.run(debug=True, port=5001)