import argparse
import ST7735
import time
import math
from datetime import datetime

from bme280 import BME280
from enviroplus import gas

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559

    ltr559 = LTR559()
except ImportError:
    import ltr559

from subprocess import PIPE, Popen, check_output
from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoMedium as UserFont
import json

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus

def write_logline(logfile, text):
    now = datetime.strftime(datetime.now(), '%d-%m-%Y %H-%M-%S')
    log_text = '{}  {}\n'.format(now, text)
    print(log_text, end='')     # also display log info, comment out if not needed
    logfile.write(log_text)


def write_log(values):
    with open("Recordings/temp.txt", "a") as logfile:
        write_logline(logfile, values)

# Read values from BME280 and return as dict
def read_bme280(bme280):
    # Compensation factor for temperature
    comp_factor = 2.25
    values = {}
    cpu_temp = get_cpu_temperature()
    raw_temp = bme280.get_temperature()  # float
    comp_temp = raw_temp - ((cpu_temp - raw_temp) / comp_factor)
    values["temperature"] = int(comp_temp)
    values["pressure(hPa)"] = round(
        int(bme280.get_pressure()), -1
    )  # round to nearest 10
    values["humidity"] = int(bme280.get_humidity())
    data = gas.read_all()
    #values["oxidised"] = int(data.oxidising / 1000)
    #values["reduced"] = int(data.reducing / 1000)
    values["nh3(Ohms)"] = int(data.nh3 / 1000)
    values["lux"] = int(ltr559.get_lux())
    return values


# Get CPU temperature to use for compensation
def get_cpu_temperature():
    process = Popen(
        ["vcgencmd", "measure_temp"], stdout=PIPE, universal_newlines=True
    )
    output, _error = process.communicate()
    return float(output[output.index("=") + 1 : output.rindex("'")])


# Get Raspberry Pi serial number to use as ID
def get_serial_number():
    with open("/proc/cpuinfo", "r") as f:
        for line in f:
            if line[0:6] == "Serial":
                return line.split(":")[1].strip()


# Check for Wi-Fi connection
def check_wifi():
    if check_output(["hostname", "-I"]):
        return True
    else:
        return False


# Display Raspberry Pi serial and Wi-Fi status on LCD
def display_status(disp):
    # Width and height to calculate text position
    WIDTH = disp.width
    HEIGHT = disp.height
    # Text settings
    font_size = 12
    font = ImageFont.truetype(UserFont, font_size)

    wifi_status = "connected" if check_wifi() else "disconnected"
    text_colour = (255, 255, 255)
    back_colour = (0, 170, 170) if check_wifi() else (85, 15, 15)
    device_serial_number = get_serial_number()
    message = "{}\nWi-Fi: {}\n".format(
        device_serial_number, wifi_status
    )
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    size_x, size_y = draw.textsize(message, font)
    x = (WIDTH - size_x) / 2
    y = (HEIGHT / 2) - (size_y / 2)
    draw.rectangle((0, 0, 160, 80), back_colour)
    draw.text((x, y), message, font=font, fill=text_colour)
    disp.display(img)



def continuous_sensor_recording(frequency, timeout):
    # Timeout
    #timer = time.time() + 60 * timeout
    count = 0
	# Raspberry Pi ID
    device_serial_number = get_serial_number()
    device_id = "raspi-" + device_serial_number

    bus = SMBus(1)

    # Create BME280 instance
    bme280 = BME280(i2c_dev=bus)

    # Create LCD instance
    disp = ST7735.ST7735(
        port=0, cs=1, dc=9, backlight=12, rotation=270, spi_speed_hz=10000000
    )

    # Initialize display
    disp.begin()

    # Display Raspberry Pi serial and Wi-Fi status
    print("RPi serial: {}".format(device_serial_number))
    print("Wi-Fi: {}\n".format("connected" if check_wifi() else "disconnected"))

    # Main loop to read data, display
    while True:
        print(count)
        if (count > (timeout*60/frequency)):
            print("breaking sensor")
            break  
        try:
            values = read_bme280(bme280)
            write_log(values)
            count = count + 1
            time.sleep(frequency)
            
        except Exception as e:
            print(e)
    print("done sensor")

def triggered_grab_data(startTime, before, after, frequency):
    print(startTime)
    duration = before + after
    time.sleep(after)
    temp = ""
    n = math.ceil(duration/frequency)
    with open("Recordings/temp.txt", "r") as logfile:
        # Skips text before the beginning of the interesting block:
        for line in (logfile.readlines() [-n:]):
            print(line, end ='')
            print("LOG:" + line)
            temp += line

    triggered_output_log(startTime, temp)
            
def triggered_output_log(startTime, temp):
    with open("Recordings/" + startTime.strftime("%d-%m-%Y %H-%M-%S") + "_tiggered_log.txt", "a") as logfile:
        logfile.write(temp)

        
def main():
    # Raspberry Pi ID
    device_serial_number = get_serial_number()
    device_id = "raspi-" + device_serial_number

    bus = SMBus(1)

    # Create BME280 instance
    bme280 = BME280(i2c_dev=bus)

    # Create LCD instance
    disp = ST7735.ST7735(
        port=0, cs=1, dc=9, backlight=12, rotation=270, spi_speed_hz=10000000
    )

    # Initialize display
    disp.begin()

    # Display Raspberry Pi serial and Wi-Fi status
    print("RPi serial: {}".format(device_serial_number))
    print("Wi-Fi: {}\n".format("connected" if check_wifi() else "disconnected"))

    # Main loop to read data, display, and send over mqtt
    while True:
        try:
            values = read_bme280(bme280)
            values["serial"] = device_serial_number
            print(values)
            time.sleep(3)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    main()
