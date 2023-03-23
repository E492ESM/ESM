import pyaudio
import wave
import time
from collections import deque
from threading import Thread
from time import sleep
from datetime import datetime, timedelta
import gdown
import RPi.GPIO as GPIO

from EnviroSensors import continuous_sensor_recording, triggered_grab_data

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

#default settings, should be overwritten by the config update
moduleName = "ESM"
contLength = 30
contClipLength = 20
trigLengthBefore = 15
trigLengthAfter = 15

def updateConfig():
    #Download the config file from Google Drive
    url = 'https://drive.google.com/uc?id=1JLCfnInWqMLgsnM06CptSa6VYjuuY1tZ'
    output = '/home/pi/Desktop/ESM_Prod/config.txt'
    gdown.download(url, output, quiet=False)

    #Parse config file
    with open('/home/pi/Desktop/ESM_Prod/config.txt') as f:
        moduleName = f.readline().strip()
        contLength = f.readline().strip()
        contClipLength = f.readline().strip()
        trigLengthBefore = f.readline().strip()
        trigLengthAfter = f.readline().strip()
        accelSensSelect = f.readline().strip()
        gyroSensSelect = f.readline().strip()

    #Stripping off the variable name and converting to int
    moduleName = moduleName.split(":")[1].lstrip()
    contLength = int(contLength.split(":")[1].lstrip())
    contClipLength = int(contClipLength.split(":")[1].lstrip())
    trigLengthBefore = int(trigLengthBefore.split(":")[1].lstrip())
    trigLengthAfter = int(trigLengthAfter.split(":")[1].lstrip())
    accelSensSelect = accelSensSelect.split(":")[1].lstrip()
    gyroSensSelect = gyroSensSelect.split(":")[1].lstrip()

    return moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter

#Continuous Mode
def startContRecording(contLength, contClipLength):
    #Based on code from https://realpython.com/playing-and-recording-sound-python/
    continuousModeLength = contLength*60 # Length of recording in seconds
    maxAudioClipLength = contClipLength*60
    maxFramesPerClip = int(samplingRate/chunk*maxAudioClipLength)

    pc = pyaudio.PyAudio()  # Create an interface to PortAudio

    startTime = datetime.now()
    stream = pc.open(format=sampleFormat, channels=channels, rate=samplingRate, frames_per_buffer=chunk, input=True)
        
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
        # Once we've reached the max audio clip length, swap to the other frame list and start processing the clip
        if numFrames == maxFramesPerClip:
            filename = "Recordings/" + moduleName + " - " + startTime.strftime("%d-%m-%Y %H-%M") + " " + str(clipNumber) + ".wav"
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

    filename = "Recordings/" + moduleName + " - " + startTime.strftime("%d-%m-%Y %H-%M") + " " + str(clipNumber) + ".wav"
    if len(activeFrameList) > 0:
        # Save the recorded data as a WAV file
        wf = wave.open(filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(pc.get_sample_size(sampleFormat))
        wf.setframerate(samplingRate)
        wf.writeframes(b''.join(activeFrameList))
        wf.close()

    # Stop and close the stream 
    stream.stop_stream()
    stream.close()
    # Terminate the PortAudio interface
    pc.terminate()
    print("Recording saved")
    return

def main():
    moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter = updateConfig()
    p = pyaudio.PyAudio()  # Create an interface to PortAudio
    stream = p.open(format=sampleFormat, channels=channels, rate=samplingRate, frames_per_buffer=chunk, input=True)
    # Create fixed-size buffer for triggered mode
    audioQueue = deque(maxlen=int((trigLengthBefore+trigLengthAfter)*samplingRate/chunk))
    
    # Frequency of the sensor recordings in seconds
    frequency = 5
    
    # Starts recording from Enviro+ board
    sensors_thread = Thread(target=continuous_sensor_recording, args=(frequency, contLength,))
    sensors_thread.start()
    
    # Stabilize sensors 
    time.sleep(10)
    
    lastContRecording = datetime(2000, 1, 1)
    lastTrigRecording = datetime(2000, 1, 1)
    startTrigTime = datetime(2000, 1, 1)
    startTrig = False
    while True:
        audioQueue.append(stream.read(chunk))
        
        # Continuous Mode
        if GPIO.event_detected(5):
            # Previous recording should end before a new one starts
            if datetime.now() - timedelta(minutes=contLength) > lastContRecording:
                lastContRecording = datetime.now()
                moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter = updateConfig()
                print("Recording for " + str(contLength) + " minutes")
                micThread = Thread(target=startContRecording, args=(contLength, contClipLength,))
                micThread.start()
        # Triggered Mode
        if GPIO.event_detected(6) and not startTrig:
                lastTrigRecording = datetime.now()
                startTrigTime = datetime.now()
                startTrig = True
                print("Recording grab triggered")
                triggered_sensor_thread = Thread(target=triggered_grab_data, args=(startTrigTime, trigLengthBefore, trigLengthAfter, frequency,))
                triggered_sensor_thread.start()
            
        # Save window of audio around trigger
        if startTrig and (datetime.now() - timedelta(seconds=trigLengthAfter) > startTrigTime):
            savedAudioQueue = audioQueue
            frames = []
            for elem in savedAudioQueue:
                frames.append(elem)
                    
            filename = "Recordings/" + moduleName + " - " + startTrigTime.strftime("%d-%m-%Y %H-%M-%S") + ".wav"
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
    




