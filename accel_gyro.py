'''
        Interfacing Raspberry Pi with MPU6050
        https://www.electronicwings.com/raspberry-pi/mpu6050-accelerometergyroscope-interfacing-with-raspberry-pi

        Specifications
        https://www.electronicwings.com/sensors-modules/mpu6050-gyroscope-accelerometer-temperature-sensor-module

        Plotting
        https://makersportal.com/blog/2019/11/11/raspberry-pi-python-accelerometer-gyroscope-magnetometer#interfacing=
'''
import smbus,time,datetime
from time import sleep
import numpy as np
import matplotlib.pyplot as plt

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

#default settings, should be overwritten by the config update
accel_sensitivity = ACCEL_VERY_LOW_SENS
gyro_sensitivity = GYRO_VERY_LOW_SENS
accelSensSelect = 'vlow'
gyroSensSelect = 'vlow'

#Polling speed (sec)
ACCEL_GYRO_SLEEP_TIME = 1

#Number of points for testing
NUM_POINTS = 1000

def get_config():
    #Download the config file from Google Drive
    #url = 'https://drive.google.com/uc?id=1JLCfnInWqMLgsnM06CptSa6VYjuuY1tZ'
    #output = '/home/pi/Desktop/ESM/config.txt'
    #gdown.download(url, output, quiet=False)

    #Parse config file
    global accel_sensitivity, gyro_sensitivity, accelSensSelect, gyroSensSelect
    
    with open('/home/pi/Desktop/ESM/config.txt') as f:
        moduleName = f.readline().strip()
        contLength = f.readline().strip()
        contClipLength = f.readline().strip()
        trigLengthBefore = f.readline().strip()
        trigLengthAfter = f.readline().strip()
        accelSensSelect = f.readline().strip()
        gyroSensSelect = f.readline().strip()


    #Stripping off the variable name and converting to int
    accelSensSelect = accelSensSelect.split(":")[1].lstrip()
    gyroSensSelect = gyroSensSelect.split(":")[1].lstrip()


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
    global Ax, Ay, Az, Gx, Gy, Gz

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


def prep_graph():
    global mpu6050_str, mpu6050_vec,t_vec
    
    plt.style.use('ggplot') # matplotlib visual style setting
    # prepping for visualization
    mpu6050_str = ['accel-x','accel-y','accel-z','gyro-x','gyro-y','gyro-z']
    mpu6050_vec,t_vec = [],[]


def plot_data():
    global mpu6050_str, mpu6050_vec,t_vec
    
    t_vec = np.subtract(t_vec,t_vec[0])

    # plot the resulting data in 2-subplots, with each data axis
    fig,axs = plt.subplots(2,1,figsize=(12,7),sharex=True)
    cmap = plt.cm.Set1

    ax = axs[0] # plot accelerometer data
    for zz in range(0,np.shape(mpu6050_vec)[1]-3):
        data_vec = [ii[zz] for ii in mpu6050_vec]
        ax.plot(t_vec,data_vec,label=mpu6050_str[zz],color=cmap(zz))
    ax.legend(bbox_to_anchor=(1.12,0.9))
    ax.set_ylabel('Acceleration [g]',fontsize=12)

    ax2 = axs[1] # plot gyroscope data
    for zz in range(3,np.shape(mpu6050_vec)[1]):
        data_vec = [ii[zz] for ii in mpu6050_vec]
        ax2.plot(t_vec,data_vec,label=mpu6050_str[zz],color=cmap(zz))
    ax2.legend(bbox_to_anchor=(1.12,0.9))
    ax2.set_ylabel('Angular Vel. [dps]',fontsize=12)

    fig.align_ylabels(axs)
    plt.show()




bus = smbus.SMBus(1)    # or bus = smbus.SMBus(0) for older version boards
Device_Address = 0x68   # MPU6050 device address

get_config()
MPU_Init()
prep_graph()

print ("---- Reading Data, Settings: ----")
print (" Sensitivity of Accelerometer: " + str(accelSensSelect) + ", " + str(accel_sensitivity))
print (" Sensitivity of Gyroscope: " + str(gyroSensSelect) + ", " + str(gyro_sensitivity))
print("")

'''
while True:
    get_data()

    # print ("Gx=%.2f" %Gx, u'\u00b0'+ "/s", "\tGy=%.2f" %Gy, u'\u00b0'+ "/s", "\tGz=%.2f" %Gz, u'\u00b0'+ "/s", "\tAx=%.2f g" %Ax, "\tAy=%.2f g" %Ay, "\tAz=%.2f g" %Az)
    print("Accelerometer [g] \tAx=%.2f" %Ax, "\tAy=%.2f" %Ay, "\tAz=%.2f" %Az)
    print("Gyroscope ["u'\u00b0'+ "/s] \tGx=%.2f" %Gx, "\tGy=%.2f" %Gy, "\tGz=%.2f" %Gz)
    print("")


    sleep(ACCEL_GYRO_SLEEP_TIME)
'''

for i in range(0,NUM_POINTS):
    get_data()
    t_vec.append(time.time()) # capture timestamp
    mpu6050_vec.append([Ax,Ay,Az,Gx,Gy,Gz])

plot_data()

