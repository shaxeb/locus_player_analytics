from numba.pycc import CC
import numpy as np
from numba import types


cc = CC('calculate_sports_numba')

@cc.export('calculate_speed', '(float64, float64, float64, float64[:], float64, float64, float64, float64, int64)')
def calculate_speed(initial_ts, reference_ts, prev_ts, max_speed, last_nonzero_speed, threshold, ts, az, status):
    if initial_ts == 0:
        initial_ts = ts
    else:
        c_ts = ts - initial_ts

    if reference_ts != -1:
        reference_ts = ts
    dt = ts - prev_ts if prev_ts != -1 else 0
    prev_ts = ts

    if az != -1:
        v_z = az * dt
    else:
        v_z = 0

    velocity_value = abs(round(v_z, 1))

    max_speed[:-1] = max_speed[1:]
    max_speed[-1] = velocity_value
    max_velocity = np.mean(max_speed)

    if last_nonzero_speed != -1:
        last_nonzero_speed = max_velocity

    if status == 0:
        last_nonzero_speed = 0
        max_velocity = 0
    else:
        if max_velocity > 0:
            last_nonzero_speed = max_velocity
    speed = last_nonzero_speed * 3.6 * 4.5

    return speed, initial_ts, reference_ts, prev_ts, max_speed, last_nonzero_speed, threshold, ts, az, status

@cc.export('calculate_acceleration', 'Tuple((f8, f8, f8, f8, f8, f8, f8, f8, f8)) (f8, f8, f8, f8, f8, f8, f8, f8, f8)')
def calculate_acceleration(prev_acc, current_acc, prev_time, current_time, ax, ay, az, ts, reference_ts):
    acc_magnitude = (ax**2 + ay**2 + az**2)**0.5 - 9.81
    if ax != -1 and ay != -1 and az != -1:
        prev_acc = current_acc
        current_acc = acc_magnitude
        prev_time = current_time
        if reference_ts != -1:
            current_time = ts - reference_ts
    else:
        prev_acc = 0
        current_acc = 0
        prev_time = 0
        current_time = 0
    return prev_acc, current_acc, prev_time, current_time, ax, ay ,az, ts, reference_ts

@cc.export('detect_steps', 'Tuple((f8, f8, f8, i8, f8, f8, f8, f8, i8)) (f8, f8, f8, i8, f8, f8, f8, f8, i8)')
def detect_steps(prev_acc, current_acc, threshold, step_counter, prev_ts, step_b_ts, step_e_ts, ts, status):
    if prev_acc != -1 and status != 0 and ts!=0:
        if prev_acc < threshold <= current_acc:
            step_b_ts = ts
        elif prev_acc >= threshold > current_acc:
            step_e_ts = ts
            if step_b_ts != -1 and step_e_ts > step_b_ts:
                    step_counter += 1
    return prev_acc, current_acc, threshold, step_counter, prev_ts, step_b_ts, step_e_ts, ts, status


@cc.export('detect_jump', 'Tuple((int64, float64[:], float64[:], float64))(float64[:], float64[:], float64, int64, float64)')
def detect_jump(acc_buffer, ts_buffer, jump_threshold, jump_count, last_jump_time):
    # Low-pass filter
    alpha = 0.2
    filtered_acc = np.zeros_like(acc_buffer)
    filtered_acc[0] = acc_buffer[0]
    for i in range(1, len(acc_buffer)):
        filtered_acc[i] = alpha * acc_buffer[i] + (1 - alpha) * filtered_acc[i-1]
    
    # Peak detection
    min_distance = 5
    for i in range(1, len(filtered_acc) - 1):
        if (filtered_acc[i] > filtered_acc[i-1] and 
            filtered_acc[i] > filtered_acc[i+1] and 
            filtered_acc[i] > jump_threshold):
            if (i == 1 or i - 1 >= min_distance):
                if (ts_buffer[i] - last_jump_time) > 0.3:  # 0.3 is the cooldown time
                    jump_count += 1
                    last_jump_time = ts_buffer[i]
    
    print(f"Jump counts from calculate_sports_numba: {jump_count}")
    
    return jump_count, acc_buffer, ts_buffer, last_jump_time

@cc.export('is_acceleration_phase', (types.float64[:],))
def is_acceleration_phase(speed_history):
    return speed_history[-1] > 1.11

@cc.export('is_max_velocity_phase', (types.float64[:],))
def is_max_velocity_phase(speed_history):
    if len(speed_history) < 10:
        return False
    return np.all(speed_history[-10:] > 4)

@cc.export('is_deceleration_phase', (types.float64[:],))
def is_deceleration_phase(speed_history):
    return speed_history[-1] <= 1.11 and np.any(speed_history[:-1] > 4)

cc.compile()