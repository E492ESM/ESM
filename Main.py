import pyaudio
import wave
from collections import deque
import threading
from time import sleep
from datetime import datetime
import gdown

#Mic Configuration
chunk = 1024  # Record in chunks of 1024 samples
sampleFormat = pyaudio.paInt16  # 16 bits per sample
channels = 1
samplingRate = 384000  # Record at 384000 samples per second

#User Configuration
#Download the config file from Google Drive
url = 'https://drive.google.com/uc?id=1JLCfnInWqMLgsnM06CptSa6VYjuuY1tZ'
output = 'home/pi/Desktop/ESM/config.txt'
gdown.download(url, output, quiet=False)

#Parse config file
with open('home/pi/Desktop/ESM/config.txt') as f:
    moduleName = f.readline().strip()
    contLength = f.readline().strip()
    trigLengthBefore = f.readline().strip()
    trigLengthAfter = f.readline().strip()

#Stripping off the variable name and converting to int
moduleName = moduleName.split(":")[1].lstrip()
contLength = int(contLength.split(":")[1].lstrip())
trigLengthBefore = int(trigLengthBefore.split(":")[1].lstrip())
trigLengthAfter = int(trigLengthAfter.split(":")[1].lstrip())


#Continuous Mode
#Based on code from https://realpython.com/playing-and-recording-sound-python/
continuousModeLength = contLength*60 # Length of recording in seconds

p = pyaudio.PyAudio()  # Create an interface to PortAudio

startTime = datetime.now()
stream = p.open(format=sampleFormat, channels=channels, rate=samplingRate, frames_per_buffer=chunk, input=True)

frames = []  # Initialize array to store frames

# Store data in chunks
for i in range(0, int(samplingRate/chunk*continuousModeLength)):
    data = stream.read(chunk)
    frames.append(data)

# Stop and close the stream 
stream.stop_stream()
stream.close()
# Terminate the PortAudio interface
p.terminate()

filename = moduleName + " - " + startTime.strftime("%d-%m-%Y %H,%M,%S") + ".wav"

# Save the recorded data as a WAV file
wf = wave.open(filename, 'wb')
wf.setnchannels(channels)
wf.setsampwidth(p.get_sample_size(sampleFormat))
wf.setframerate(samplingRate)
wf.writeframes(b''.join(frames))
wf.close()


#Triggered Mode
p = pyaudio.PyAudio()  # Create an interface to PortAudio

startTime = datetime.now()
stream = p.open(format=sampleFormat, channels=channels, rate=samplingRate, frames_per_buffer=chunk, input=True)

audioQueue = deque(maxlen=int((trigLengthBefore+trigLengthAfter)*samplingRate/chunk))

for i in range (0, int(samplingRate/chunk*continuousModeLength)):
    audioQueue.append(stream.read(chunk))

# Stop and close the stream 
stream.stop_stream()
stream.close()
# Terminate the PortAudio interface
p.terminate()

frames = []
for elem in audioQueue:
    frames.append(elem)

filename = moduleName + " - " + startTime.strftime("%d-%m-%Y %H,%M,%S") + ".wav"

# Save the recorded data as a WAV file
wf = wave.open(filename, 'wb')
wf.setnchannels(channels)
wf.setsampwidth(p.get_sample_size(sampleFormat))
wf.setframerate(samplingRate)
wf.writeframes(b''.join(frames))
wf.close()
