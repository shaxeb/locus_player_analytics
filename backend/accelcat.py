#!/usr/bin/env python3
# -*- coding: utf-8 -*-

''' Accelerometer, Velocity and Displacement python service'''
import time
import datetime
import numpy
import pandas
import json
import math
from microstacknode.hardware.accelerometer.mma8452q import MMA8452Q

G_RANGE = 2
GRAVITY = 9.80665 # in SI units (m/s^2)
SAMPLE_CALIBRATION = 1024 # number of sampples
SAMPLE_FILTERING = 100 # rolling mean samples number
WINDOW_FILTERING = 20 # rolling mean window
#T = 0.2  # seconds. Sample rate (5 Hz)
T = 0.02  # seconds. Sample rate (50 Hz)
#T = 0.002  # seconds. Sample rate (500 Hz)
R = 1 # sample transport rate in minutes

REPOSITORY = "./repository";
HUBNAME = "accelcat";

# calibration: This calibration routine removes the acceleration offset component in the sensor output due
# to the earth's gravity (static acceleration)
def auto_calibration():
    sstatex = 0
    sstatey = 0
    sstatez = 0
    for i in range(0, SAMPLE_CALIBRATION):
        ms = accelerometer.get_xyz_ms2()
        
        sstatex = sstatex + ms['x']
        sstatey = sstatey + ms['y']
        sstatez = sstatez + ms['z']

    sstatex = sstatex / SAMPLE_CALIBRATION  # m/s^2
    sstatey = sstatey / SAMPLE_CALIBRATION # m/s^2
    sstatez = (sstatez / SAMPLE_CALIBRATION) - GRAVITY # m/s^2

    return (sstatex, sstatey, sstatez)

# low pass filtering: pandas rolling mean
def low_pass_filtering(s, N):
    # return pandas.rolling_mean(x, N)[N-1:]
    return s.rolling(window=N, win_type='triang').mean()
           
if __name__ == '__main__':
    # STEP01: initialize transport time and final meassures
    ti = time.time()

    AxF=0
    AyF=0
    AzF=0
    VxF=0
    VyF=0
    VzF=0
    DxF=0
    DyF=0
    DzF=0

    # connect to the accelerometer device MMA8452Q
    with MMA8452Q() as accelerometer:
        # STEP02: Configure accelerometer
        accelerometer.standby()
        accelerometer.set_g_range(G_RANGE)
        accelerometer.activate()
        print("Accelerometer G range configuration = {}".format(G_RANGE) + "\n")
        time.sleep(T)

        # STEP03: auto-calibration
        Cax, Cay, Caz = auto_calibration()
        print('----')
        print('Auto-calibration data | x: {}, y: {}, z: {}'.format(Cax, Cay, Caz) + "\n")
        
        Aix = 0
        Aiy = 0
        Aiz = 0
        Vix = 0
        Viy = 0
        Viz = 0
        
        while True:
            # STEP04: apply a convolution filter to the three axis (moving average filter)
            # extract the raw data from the three accelerometer axis
            index = range(0, SAMPLE_FILTERING)
            filtval = []
            for i in index:
                filtval.append(accelerometer.get_xyz_ms2())

            # create the data frame from the raw data to be filtered
            dataFrame = pandas.DataFrame(filtval, index=index, columns=list('xyz'))
            
            # apply the convolution filter to the data frame
            dataFiltered = low_pass_filtering(dataFrame, WINDOW_FILTERING)

            for index, ms in dataFiltered.iterrows():
               # STEP05: calculate displacement and velocity using a trapezoidal method integration
               # velocity integration from acceleration
               # displacement integration from velocity
               # remove gravity from z axis
               if numpy.isnan(ms['z']):
                   continue

               if ms['x'] >=0:
                   Ax = (ms['x'] - Cax) * 1000 # mm/s^2
                   Vx = Aix * T + abs((Ax - Aix) / 2) * T # mm/s
                   Dx = Vix * T + abs((Vx - Vix) / 2) * T # mm
               else:
                   Ax = (ms['x'] - Cax) * 1000 # mm/s^2
                   Vx = Aix * T - abs((Ax - Aix) / 2) * T # mm/s
                   Dx = Vix * T - abs((Vx - Vix) / 2) * T # mm
                
               Aix = Ax
               Vix = Vx

               if ms['y'] >=0:
                   Ay = (ms['y'] - Cay) * 1000 # mm/s^2
                   Vy = Aiy * T + abs((Ay - Aiy) / 2) * T # mm/s
                   Dy = Viy * T + abs((Vy - Viy) / 2) * T # mm
               else:
                   Ay = (ms['y'] - Cay) * 1000 # mm/s^2
                   Vy = Aiy * T - abs((Ay - Aiy) / 2) * T # mm/s
                   Dy = Viy * T - abs((Vy - Viy) / 2) * T # mm           

               Aiy = Ay
               Viy = Vy

               if ms['z'] >=0:
                   Az = (ms['z'] - Caz - GRAVITY) * 1000 # mm/s^2
                   Vz = Aiz * T + abs((Az - Aiz) / 2) * T # mm/s
                   Dz = Viz * T + abs((Vz - Viz) / 2) * T # mm
               else:
                   Az = (ms['z'] - Caz + GRAVITY) * 1000 # mm/s^2
                   Vz = Aiz * T - abs((Az - Aiz) / 2) * T # mm/s
                   Dz = Viz * T - abs((Vz - Viz) / 2) * T # mm

               Aiz = Az                                 
               Viz = Vz
               
               # STEP06: get the maximun value in the three axis
               if VxF < abs(Vx):
                  AxF = abs(Ax)
                  VxF = abs(Vx)
                  DxF = abs(Dx)		              

               if VyF < abs(Vy):
                  AyF = abs(Ay)
                  VyF = abs(Vy)
                  DyF = abs(Dy)

               if VzF < abs(Vz):
                  AzF = abs(Az)
                  VzF = abs(Vz)
                  DzF = abs(Dz)
               
               # STEP07: create JSON data after transport rate
               if (time.time() - ti) > R * 60:
                 data = {'tstamp': datetime.datetime.now().isoformat(),
                         'D': {'x': DxF,
                               'y': DyF,
                               'z': DzF},
                         'V': {'x': VxF,
                               'y': VyF,
                               'z': VzF},
                         'A': {'x': AxF,
                               'y': AyF,
                               'z': AzF}}
                       
                 # STEP08: publish save JSON result on repository folder
                 f = open(REPOSITORY + '/' + HUBNAME + '_' + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.json', 'w')
                 f.write(json.dumps(data))
                 f.close()

                 # logging result
                 print('----')
                 print('Json file saved correctly at {}'.format(datetime.datetime.now()))
                 print('Acceleration [mm/s^2] | x: {:.2f}, y: {:.2f}, z: {:.2f}'.format(AxF, AyF, AzF))
                 print('Velocity [mm/s] | x: {:.2f}, y: {:.2f}, z: {:.2f}'.format(VxF, VyF, VzF))
                 print('Distance [mm] | x: {:.2f}, y: {:.2f}, z: {:.2f}'.format(DxF, DyF, DzF))
                 print("\n")

                 # initialize transport time and final meassures
                 ti = time.time()

                 AxF=0
                 AyF=0
                 AzF=0
                 VxF=0
                 VyF=0
                 VzF=0
                 DxF=0
                 DyF=0
                 DzF=0

               # next data (T sample rate) 
               time.sleep(T)
