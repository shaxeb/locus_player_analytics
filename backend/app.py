'''
1. export data option
2. threshold customization option
3. gragh zoom in or zoom out seek
4. error handling for out of bound selection of time period
'''

from flask import Flask, jsonify, request
from flask_cors import CORS
from database_handler import DatabaseHandler
import numpy as np
from scipy.signal import find_peaks
import math

app = Flask(__name__)
CORS(app)

db = DatabaseHandler()

def calculate_speed(x_positions, y_positions, timestamps):
    dt = np.diff(timestamps) / 1_000_000  # Convert microseconds to seconds
    dx = np.diff(x_positions)
    dy = np.diff(y_positions)
    
    speeds = np.sqrt(dx**2 + dy**2) / dt
    speeds = np.concatenate(([0], speeds))  # Prepend 0 for the first timestamp
    return speeds

def calculate_acceleration(ax, ay, az):
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
                last_jump_time = i  # Update last jump time

    return jump_count

@app.route('/api/players', methods=['GET'])
def get_players():
    connection = db.connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("SELECT player_id, name FROM players WHERE name IS NOT NULL")
    players = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return jsonify(players)

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
    timestamps = np.array([d['timestamp_micros'] for d in tracking_data])
    x_positions = np.array([d['x_position'] for d in tracking_data])
    y_positions = np.array([d['y_position'] for d in tracking_data])
    
    ax = np.array([d['accel_x'] for d in tracking_data])
    ay = np.array([d['accel_y'] for d in tracking_data])
    az = np.array([d['accel_z'] for d in tracking_data])
    
    # Calculate metrics
    speeds = calculate_speed(x_positions, y_positions, timestamps)
    acc_magnitude = calculate_acceleration(ax, ay, az)
    step_count = detect_steps(acc_magnitude, threshold=2.0)  # Example threshold
    jump_count = detect_jumps(acc_magnitude, jump_threshold=4.0)  # Example threshold
    
    avg_speed = np.mean(speeds)
    max_speed = np.max(speeds)
    
    return jsonify({
        'speeds': {
            'data': speeds.tolist(),
            'timestamps': timestamps[1:].tolist(),  # Exclude the first timestamp for speed
            'average': float(avg_speed),
            'max': float(max_speed)
        },
        'steps': {
            'count': step_count,
            'timestamps': [],  # You can add timestamps if needed
            'magnitudes': []   # You can add magnitudes if needed
        },
        'jumps': {
            'count': jump_count,
            'timestamps': [],  # You can add timestamps if needed
            'magnitudes': []   # You can add magnitudes if needed
        },
        'acceleration_magnitude': {
            'data': acc_magnitude.tolist(),
            'timestamps': timestamps.tolist()
        }
    })

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