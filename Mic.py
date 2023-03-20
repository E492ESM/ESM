import pyaudio
import wave
from collections import deque
from threading import Thread
from time import sleep
from datetime import datetime
import gdown
import RPi.GPIO as GPIO

from EnviroSensors import continuous_sensor_recording

#Mic Configuration
chunk = 9600  # Record in chunks of 9600 samples
sampleFormat = pyaudio.paInt16  # 16 bits per sample
channels = 1
samplingRate = 384000  # Record at 384000 samples per second

#default settings, should be overwritten by the config update
moduleName = "ESM"
contLength = 60
contClipLength = 30
trigLengthBefore = 15
trigLengthAfter = 15

def updateConfig():
    #Download the config file from Google Drive
    url = 'https://drive.google.com/uc?id=1JLCfnInWqMLgsnM06CptSa6VYjuuY1tZ'
    output = 'home/pi/Desktop/ESM/config.txt'
    gdown.download(url, output, quiet=False)

    #Parse config file
    with open('home/pi/Desktop/ESM/config.txt') as f:
        moduleName = f.readline().strip()
        contLength = f.readline().strip()
        contClipLength = f.readline().strip()
        trigLengthBefore = f.readline().strip()
        trigLengthAfter = f.readline().strip()

    #Stripping off the variable name and converting to int
    moduleName = moduleName.split(":")[1].lstrip()
    contLength = int(contLength.split(":")[1].lstrip())
    contClipLength = int(contClipLength.split(":")[1].lstrip())
    trigLengthBefore = int(trigLengthBefore.split(":")[1].lstrip())
    trigLengthAfter = int(trigLengthAfter.split(":")[1].lstrip())

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
        #Once we've reached the max audio clip length, swap to the other frame list and start processing the clip
        if numFrames == maxFramesPerClip:
            filename = moduleName + " - " + startTime.strftime("%d-%m-%Y %H-%M-%S") + " " + str(clipNumber) + ".wav"
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

    filename = moduleName + " - " + startTime.strftime("%d-%m-%Y %H-%M-%S") + " " + str(clipNumber) + ".wav"
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

def main():
    #pin settings
    GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
    GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(31, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter = updateConfig()
    p = pyaudio.PyAudio()  # Create an interface to PortAudio
    stream = p.open(format=sampleFormat, channels=channels, rate=samplingRate, frames_per_buffer=chunk, input=True)
    #Create fixed-size buffer for triggered mode
    audioQueue = deque(maxlen=int((trigLengthBefore+trigLengthAfter)*samplingRate/chunk))

    sensors_thread = Thread(target=continuous_sensor_recording)
    sensors_thread.start()

    while True:
        audioQueue.append(stream.read(chunk))
        #Continuous Mode
        if GPIO.input(29) == GPIO.HIGH:
            #Update settings and start a new thread to record in continuous mode
            moduleName, contLength, contClipLength, trigLengthBefore, trigLengthAfter = updateConfig()
            startTime = datetime.now()
            thread = Thread(target=startContRecording, args=(contLength, contClipLength))
            thread.start()
            #Once the recording is done, the spawned thread will end - no need to join
        #Triggered Mode    
        if GPIO.input(31) == GPIO.HIGH:
            #Save the audio data to a separate queue for processing
            savedAudioQueue = audioQueue
            startTime = datetime.now()
            frames = []
            for elem in savedAudioQueue:
                frames.append(elem)
            filename = moduleName + " - " + startTime.strftime("%d-%m-%Y %H-%M-%S") + ".wav"

            # Save the recorded data as a WAV file
            wf = wave.open(filename, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(sampleFormat))
            wf.setframerate(samplingRate)
            wf.writeframes(b''.join(frames))
            wf.close()

    # Stop and close the stream 
    stream.stop_stream()
    stream.close()
    # Terminate the PortAudio interface
    p.terminate()


if __name__ == "__main__":
    main()
    




