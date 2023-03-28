import pyaudio
import wave
import time
from collections import deque
from threading import Thread
from time import sleep
from datetime import datetime, timedelta
import smbus, time
import numpy as np
import matplotlib.pyplot as plt
import gdown
import RPi.GPIO as GPIO

from EnviroSensors import continuous_sensor_recording, grab_data

#Pin settings
GPIO.setmode(GPIO.BCM) # Use logical pin numbering
GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Respond to GND connections
GPIO.setup(6, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Respond to 3.3V/5V connections
GPIO.add_event_detect(5, GPIO.RISING)
GPIO.add_event_detect(6, GPIO.RISING)

#Mic Configuration
chunk = 9600  # Record in chunks of 9600 samples
sampleFormat = pyaudio.paInt16  # 16 bits per sample
channels = 1
samplingRate = 384000  # Record at 384000 samples per second

#Gyroscope settings
#Interfacing Raspberry Pi with MPU6050 based on: https://www.electronicwings.com/raspberry-pi/mpu6050-accelerometergyroscope-interfacing-with-raspberry-pi
#Specifications based on: https://www.electronicwings.com/sensors-modules/mpu6050-gyroscope-accelerometer-temperature-sensor-module
#Plotting based on: https://makersportal.com/blog/2019/11/11/raspberry-pi-python-accelerometer-gyroscope-magnetometer#interfacing=
#MPU6050 Registers and Address
PWR_MGMT_1   = 0x6B
SMPLRT_DIV   = 0x19
CONFIG       = 0x1A
GYRO_CONFIG  = 0x1B
INT_ENABLE   = 0x38
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F
GYRO_XOUT_H  = 0x43
GYRO_YOUT_H  = 0x45
GYRO_ZOUT_H  = 0x47

#Scaling factors for sensitivity (LSBs per dps), changes full-scale range of Accelerometer
ACCEL_HI_SENS = 16384.0 #LSBs per g, ±2g
ACCEL_MED_SENS = 8192.0 #LSBs per g, ±4g
ACCEL_LOW_SENS = 4096.0 #LSBs per g, ±8g
ACCEL_VERY_LOW_SENS = 2048.0 #LSBs per g, ±16g

#Scaling factors for sensitivity (LSBs per dps), changes full-scale range of Gyroscope
GYRO_HI_SENS = 131.0 #LSBs per dps, ±250 degrees per second (dps)
GYRO_MED_SENS = 65.5 #LSBs per dps, ±500 degrees per second (dps)
GYRO_LOW_SENS =  32.8 #LSBs per dps, ±1000 degrees per second (dps)
GYRO_VERY_LOW_SENS =  16.4 #LSBs per dps, ±2000 degrees per second (dps)


ACCEL_GYRO_SLEEP_TIME = 1 # Polling speed (sec)
NUM_POINTS = 1000 # Number of points for testing
bus = smbus.SMBus(1)    # or bus = smbus.SMBus(0) for older version boards
Device_Address = 0x68   # MPU6050 device address

#default settings, should be overwritten by the config update
moduleName = "ESM"
useMic = "y"
useEnviro = "y"
useGyro = "y"
contLength = 30
contClipLength = 20
trigLengthBefore = 15
trigLengthAfter = 15
accelSensSelect = 'vlow'
gyroSensSelect = 'vlow'

accel_sensitivity = ACCEL_VERY_LOW_SENS
gyro_sensitivity = GYRO_VERY_LOW_SENS

def updateConfig():
    #Download the config file from Google Drive
    url = 'https://drive.google.com/uc?id=1JLCfnInWqMLgsnM06CptSa6VYjuuY1tZ'
    output = '/home/pi/Desktop/ESM_Prod/config.txt'
    gdown.download(url, output, quiet=False)

    #Parse config file
    with open('/home/pi/Desktop/ESM_Prod/config.txt') as f:
        moduleName = f.readline().strip()
        useMic = f.readline().strip()
        useEnviro = f.readline().strip()
        useGyro = f.readline().strip()
        contLength = f.readline().strip()
        contClipLength = f.readline().strip()
        trigLengthBefore = f.readline().strip()
        trigLengthAfter = f.readline().strip()
        accelSensSelect = f.readline().strip()
        gyroSensSelect = f.readline().strip()

    #Stripping off the variable name and converting to int
    moduleName = moduleName.split(":")[1].lstrip()
    useMic = useMic.split(":")[1].lstrip()
    useEnviro = useEnviro.split(":")[1].lstrip()
    useGyro = useGyro.split(":")[1].lstrip()
    contLength = int(contLength.split(":")[1].lstrip())
    contClipLength = int(contClipLength.split(":")[1].lstrip())
    trigLengthBefore = int(trigLengthBefore.split(":")[1].lstrip())
    trigLengthAfter = int(trigLengthAfter.split(":")[1].lstrip())
    accelSensSelect = accelSensSelect.split(":")[1].lstrip()
    gyroSensSelect = gyroSensSelect.split(":")[1].lstrip()
    
    # Set device usage
    if (useMic == "y"):
        useMic = True
    else:
        useMic = False
    if (useEnviro == "y"):
        useEnviro = True
    else:
        useEnviro = False
    if (useGyro == "y"):
        useGyro = True
    else:
        useGyro = False

    #Sets the accelerometers sensitivity, default=hi
    if (accelSensSelect == 'hi'):
        accel_sensitivity = ACCEL_HI_SENS
    elif (accelSensSelect == 'med'):
        accel_sensitivity = ACCEL_MED_SENS
    elif (accelSensSelect == 'low'):
        accel_sensitivity = ACCEL_LOW_SENS
    elif (accelSensSelect == 'vlow'):
        accel_sensitivity = ACCEL_VERY_LOW_SENS
    else:
        accel_sensitivity = ACCEL_VERY_LOW_SENS

    #Sets the gyroscope sensitivity, default=hi
    if (gyroSensSelect == 'hi'):
        gyro_sensitivity = GYRO_HI_SENS
    elif (gyroSensSelect == 'med'):
        gyro_sensitivity = GYRO_MED_SENS
    elif (gyroSensSelect == 'low'):
        gyro_sensitivity = GYRO_LOW_SENS
    elif (gyroSensSelect == 'vlow'):
        gyro_sensitivity = GYRO_VERY_LOW_SENS
    else:
        gyro_sensitivity = GYRO_VERY_LOW_SENS 

    return moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter, accel_sensitivity, gyro_sensitivity, useMic, useEnviro, useGyro

def MPU_Init():
    #write to sample rate register
    bus.write_byte_data(Device_Address, SMPLRT_DIV, 7)
    
    #Write to power management register
    bus.write_byte_data(Device_Address, PWR_MGMT_1, 1)
    
    #Write to Configuration register
    bus.write_byte_data(Device_Address, CONFIG, 0)
    
    #Write to Gyro configuration register
    bus.write_byte_data(Device_Address, GYRO_CONFIG, 24)
    
    #Write to interrupt enable register
    bus.write_byte_data(Device_Address, INT_ENABLE, 1)


def read_raw_data(addr):
    #Accelero and Gyro value are 16-bit
    high = bus.read_byte_data(Device_Address, addr)
    low = bus.read_byte_data(Device_Address, addr+1)

    #concatenate higher and lower value
    value = ((high << 8) | low)
    
    #to get signed value from mpu6050
    if(value > 32768):
            value = value - 65536
    return value


def get_data():
    #Read Accelerometer raw value
    acc_x = read_raw_data(ACCEL_XOUT_H)
    acc_y = read_raw_data(ACCEL_YOUT_H)
    acc_z = read_raw_data(ACCEL_ZOUT_H)
        
    #Read Gyroscope raw value
    gyro_x = read_raw_data(GYRO_XOUT_H)
    gyro_y = read_raw_data(GYRO_YOUT_H)
    gyro_z = read_raw_data(GYRO_ZOUT_H)
        
    #Full scale range +/- 250 degree/C as per sensitivity scale factor
    Ax = acc_x/accel_sensitivity
    Ay = acc_y/accel_sensitivity
    Az = acc_z/accel_sensitivity
        
    Gx = gyro_x/gyro_sensitivity
    Gy = gyro_y/gyro_sensitivity
    Gz = gyro_z/gyro_sensitivity

    return [time.time(), Ax, Ay, Az, Gx, Gy, Gz]
    
#Record audio and gyroscope data in Continuous Mode
def startContRecording(contLength, contClipLength):
    #Based on code from https://realpython.com/playing-and-recording-sound-python/
    continuousModeLength = contLength*60 # Length of recording in seconds
    maxAudioClipLength = contClipLength*60
    maxFramesPerClip = int(samplingRate/chunk*maxAudioClipLength)

    pc = pyaudio.PyAudio()  # Create an interface to PortAudio

    startTime = datetime.now()
    stream = pc.open(format=sampleFormat, channels=channels, rate=samplingRate, frames_per_buffer=chunk, input=True)
    
    accelFile = open("/media/pi/DATA/Recordings/" + startTime.strftime("%d-%m-%Y %H-%M") + "_accel_data.txt", "w")
    accelFile.write("Time Ax Ay Az Gx Gy Gz \n")
        
    #Initialize arrays to store frames
    frames1 = []  
    frames2 = []

    numFrames = 0
    clipNumber = 1
    activeFrameList = frames1
    # Store data in chunks
    for i in range(0, int(samplingRate/chunk*continuousModeLength)):
        numFrames += 1
        activeFrameList.append(stream.read(chunk))
        if useMic:
            # Once we've reached the max audio clip length, swap to the other frame list and start processing the clip
            if numFrames == maxFramesPerClip:
                filename = "/media/pi/DATA/Recordings/" + startTime.strftime("%d-%m-%Y %H-%M") + " " + str(clipNumber) + ".wav"
                clipNumber += 1
                numFrames = 0

                if activeFrameList == frames1:
                    activeFrameList = frames2
                    # Save the recorded data as a WAV file
                    wf = wave.open(filename, 'wb')
                    wf.setnchannels(channels)
                    wf.setsampwidth(pc.get_sample_size(sampleFormat))
                    wf.setframerate(samplingRate)
                    wf.writeframes(b''.join(frames1))
                    wf.close()

                    frames1 = []
                else:
                    activeFrameList = frames1
                    # Save the recorded data as a WAV file
                    wf = wave.open(filename, 'wb')
                    wf.setnchannels(channels)
                    wf.setsampwidth(pc.get_sample_size(sampleFormat))
                    wf.setframerate(samplingRate)
                    wf.writeframes(b''.join(frames2))
                    wf.close()

                    frames2 = []
        
        if useGyro:        
            #Write gyroscope data to file
            accelData = get_data()
            for elem in accelData:
                accelFile.write(str(elem) + ' ')
            accelFile.write('\n')

    filename = "/media/pi/DATA/Recordings/" + startTime.strftime("%d-%m-%Y %H-%M") + " " + str(clipNumber) + ".wav"
    if len(activeFrameList) > 0:
        # Save the recorded data as a WAV file
        wf = wave.open(filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(pc.get_sample_size(sampleFormat))
        wf.setframerate(samplingRate)
        wf.writeframes(b''.join(activeFrameList))
        wf.close()
        
    accelFile.close()

    # Stop and close the stream 
    stream.stop_stream()
    stream.close()
    # Terminate the PortAudio interface
    pc.terminate()
    print("Recording saved")
    return

def main():
    time.sleep(5)
    MPU_Init()
    moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter, accel_sensitivity, gyro_sensitivity, useMic, useEnviro, useGyro = updateConfig()
    p = pyaudio.PyAudio()  # Create an interface to PortAudio
    stream = p.open(format=sampleFormat, channels=channels, rate=samplingRate, frames_per_buffer=chunk, input=True)
    # Create fixed-size buffer for triggered mode
    audioQueue = deque(maxlen=int((trigLengthBefore+trigLengthAfter)*samplingRate/chunk))
    accelQueue = deque(maxlen=int((trigLengthBefore+trigLengthAfter)*samplingRate/chunk))
    
    # Frequency of the sensor recordings in seconds
    frequency = 5
    
    if useEnviro:
        # Starts recording from Enviro+ board
        sensors_thread = Thread(target=continuous_sensor_recording, args=(frequency,))
        sensors_thread.start()
    
        # Stabilize sensors 
        time.sleep(10)
    
    lastContRecording = datetime(2000, 1, 1)
    startTrigTime = datetime(2000, 1, 1)
    startTrig = False
    while True:
        audioQueue.append(stream.read(chunk))
        accelQueue.append(get_data())
        
        # Continuous Mode
        if GPIO.event_detected(5):
            # Previous recording should end before a new one starts
            if datetime.now() - timedelta(minutes=contLength) > lastContRecording:
                lastContRecording = datetime.now()
                moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter, accel_sensitivity, gyro_sensitivity, useMic, useEnviro, useGyro = updateConfig()
                print("Recording for " + str(contLength) + " minutes")
                if useMic:
                    micThread = Thread(target=startContRecording, args=(contLength, contClipLength,))
                    micThread.start()
                if useEnviro:
                    cont_sensor_thread = Thread(target=grab_data, args=(lastContRecording, 0, contLength*60, frequency, False))
                    cont_sensor_thread.start()
        # Triggered Mode
        if GPIO.event_detected(6) and not startTrig:
                startTrigTime = datetime.now()
                startTrig = True
                print("Recording grab triggered")
                if useEnviro:
                    triggered_sensor_thread = Thread(target=grab_data, args=(startTrigTime, trigLengthBefore, trigLengthAfter, frequency, True))
                    triggered_sensor_thread.start()
            
        # Save window of audio and gyroscope data around trigger
        if startTrig and (datetime.now() - timedelta(seconds=trigLengthAfter) > startTrigTime):
            savedAudioQueue = audioQueue
            
            if useGyro:
                savedAccelQueue = accelQueue
                with open("/media/pi/DATA/Recordings/" + startTrigTime.strftime("%d-%m-%Y %H-%M-%S") + "_triggered_accel_data.txt", "w") as logfile:
                    logfile.write("Time Ax Ay Az Gx Gy Gz \n")
                    for accelList in savedAccelQueue:
                        for elem in accelList:
                            logfile.write(str(elem) + ' ')
                        logfile.write('\n')
                        
            if useMic:
                frames = []
                for elem in savedAudioQueue:
                    frames.append(elem)
                        
                filename = "/media/pi/DATA/Recordings/" + startTrigTime.strftime("%d-%m-%Y %H-%M-%S") + "_triggered.wav"
                # Save the recorded data as a WAV file
                wf = wave.open(filename, 'wb')
                wf.setnchannels(channels)
                wf.setsampwidth(p.get_sample_size(sampleFormat))
                wf.setframerate(samplingRate)
                wf.writeframes(b''.join(frames))
                wf.close()
                print("Recording saved")
            startTrig = False

    # Stop and close the stream 
    stream.stop_stream()
    stream.close()
    # Terminate the PortAudio interface
    p.terminate()

if __name__ == "__main__":
    main()
    




