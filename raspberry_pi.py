#Libraries
import paho.mqtt.client as mqtt
import asyncio
import ssl
import RPi.GPIO as GPIO
import time
import operator
import threading
import serial
from time import sleep
from picamera import PiCamera

# Imports for generating the Shared Access Signature (SAS) for authentication
from base64 import b64encode, b64decode
from hashlib import sha256
from time import time
from urllib.parse import quote_plus, urlencode
from hmac import HMAC

SIGN_KEY = 'lGA+kMJjYBgbxNgGIQdeK0YtAalkj5XvuLUfQj0hIhU='
device_id = 'pi'
iothub_name = 'seic4project.azure-devices.net'

GPIO.setwarnings(False)

GPIO.setmode(GPIO.BCM)

################################# ULTRASSOM #####################################

#set GPIO Pins
GPIO_TRIGGER = 16
GPIO_ECHO = 24
 
#Set GPIO
GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
GPIO.setup(GPIO_ECHO, GPIO.IN)

def distance():

    import time
    # set Trigger to HIGH
    GPIO.output(GPIO_TRIGGER, True)
 
    # set Trigger after 0.01ms to LOW
    sleep(0.00001)
    GPIO.output(GPIO_TRIGGER, False)
 
    StartTime = time.time()
    StopTime = time.time()
 
    # save StartTime
    while GPIO.input(GPIO_ECHO) == 0:
        StartTime = time.time()
 
    # save time of arrival
    while GPIO.input(GPIO_ECHO) == 1:
        StopTime = time.time()
 
    # time difference between start and arrival
    TimeElapsed = StopTime - StartTime
    distance = (TimeElapsed * 34300) / 2
 
    return distance

###########################################  Camera ################################

def takephoto():
    camera = PiCamera()
    camera.resolution = (640, 480)
    camera.start_preview()
    sleep(2)
    camera.capture('photo.jpg')
    camera.close()

###########################################   RTC  #################################

GPIO_SCLK = 27
GPIO_CE = 17
GPIO_IO = 18

CLK_PERIOD = 0.00001 # 10 ms

def InitiateDS1302():
  GPIO.setup(GPIO_SCLK, GPIO.OUT, initial=0)
  GPIO.setup(GPIO_CE, GPIO.OUT, initial=0)
  GPIO.setup(GPIO_IO, GPIO.OUT, initial=0)
  GPIO.output(GPIO_SCLK, 0)
  GPIO.output(GPIO_IO, 0)
  sleep(CLK_PERIOD)
  GPIO.output(GPIO_CE, 1)

def EndDS1302():
  GPIO.setup(GPIO_SCLK, GPIO.OUT, initial=0)
  GPIO.setup(GPIO_CE, GPIO.OUT, initial=0)
  GPIO.setup(GPIO_IO, GPIO.OUT, initial=0)
  GPIO.output(GPIO_SCLK, 0)
  GPIO.output(GPIO_IO, 0)
  sleep(CLK_PERIOD)
  GPIO.output(GPIO_CE, 0)

def WriteByte(Byte):
  for Count in range(8):
    sleep(CLK_PERIOD)
    GPIO.output(GPIO_SCLK, 0)

    Bit = operator.mod(Byte, 2)
    Byte = operator.truediv(Byte, 2)
    sleep(CLK_PERIOD)
    if Bit >= 1:
      GPIO.output(GPIO_IO, 1)
    else:
      GPIO.output(GPIO_IO, 0)
    sleep(CLK_PERIOD)
    GPIO.output(GPIO_SCLK, 1)


def ReadByte():
  GPIO.setup(GPIO_IO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

  Byte = 0
  for Count in range(8):
    sleep(CLK_PERIOD)
    GPIO.output(GPIO_SCLK, 1)

    sleep(CLK_PERIOD)
    GPIO.output(GPIO_SCLK, 0)
         
    sleep(CLK_PERIOD)
    Bit = GPIO.input(GPIO_IO)

    Byte |= ((2 ** Count) * Bit)
  return Byte

def dec2bcd(dec):
    rest = dec % 10
    div = int(dec / 10)
    divshift = div << 4

    return divshift + rest

def bcd2dec(bcd):
    return (((bcd & 0xF0) >> 4) * 10) + (bcd & 0x0F)

def WriteDateTime(Year, Month, Day, DayOfWeek, Hour, Minute, Second):
   
  InitiateDS1302()
  WriteByte(int("10111110", 2))
  
  SecondBCD = dec2bcd(Second)
  WriteByte(SecondBCD)
  MinuteBCD = dec2bcd(Minute)
  WriteByte(MinuteBCD)
  HourBCD = dec2bcd(Hour)
  WriteByte(HourBCD)
  DayBCD = dec2bcd(Day)
  WriteByte(DayBCD)
  MonthBCD = dec2bcd(Month)
  WriteByte(MonthBCD)
  DayOfWeekBCD = dec2bcd(DayOfWeek)
  WriteByte(DayOfWeekBCD)
  YearBCD = dec2bcd(Year)
  WriteByte(YearBCD)
  
  # Make sure write protect is turned off.
  WriteByte(int("00000000", 2))
  # Make sure trickle charge mode is turned off.
  WriteByte(int("00000000", 2))
  EndDS1302()

def ReadDateTime(DateTime):

  DOW = [ "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday" ]

  InitiateDS1302()
  WriteByte(int("10111111", 2))
  Data = ""

  SecondBCD = ReadByte()
  DateTime["Second"] = bcd2dec(SecondBCD)
  MinuteBCD = ReadByte()
  DateTime["Minute"] = bcd2dec(MinuteBCD)
  HourBCD = ReadByte()
  DateTime["Hour"] = bcd2dec(HourBCD)
  DayBCD = ReadByte()
  DateTime["Day"] = bcd2dec(DayBCD)
  MonthBCD = ReadByte()
  DateTime["Month"] = bcd2dec(MonthBCD)
  DayOfWeekBCD = ReadByte()
  DateTime["DayOfWeek"] = bcd2dec(DayOfWeekBCD)
  YearBCD = ReadByte() 
  DateTime["Year"] = bcd2dec(YearBCD)
  
  Data = DOW[DateTime["DayOfWeek"]] + " " + format(DateTime["Year"] + 2000, "04d") + "-" + format(DateTime["Month"], "02d") + "-" + format(DateTime["Day"], "02d")
  Data += " " + format(DateTime["Hour"], "02d") + ":" + format(DateTime["Minute"], "02d")

  EndDS1302()
  return Data

# Initiate DS1302 communication.
InitiateDS1302()
# Make sure write protect is turned off.
WriteByte(int("10001110", 2))
WriteByte(int("00000000", 2))
# Make sure trickle charge mode is turned off.
WriteByte(int("10010000", 2))
WriteByte(int("00000000", 2))
# End DS1302 communication.
EndDS1302()

#################################### PIC #######################################
ser = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)

##################################### AZURE #####################################
# Asyncio loop
loop = asyncio.new_event_loop()

# Not yet connected to the MQTT server
connected = False

# SAS token generation function
def generate_sas_token(uri, key, policy_name, expiry=3600):
    ttl = time() + expiry
    sign_key = "%s\n%d" % ((quote_plus(uri)), int(ttl))
    print(sign_key)
    signature = b64encode(HMAC(b64decode(key), sign_key.encode('utf-8'), sha256).digest())

    rawtoken = {
        'sr' :  uri,
        'sig': signature,
        'se' : str(int(ttl))
    }

    if policy_name is not None:
        rawtoken['skn'] = policy_name

    return 'SharedAccessSignature ' + urlencode(rawtoken)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print('Connection result --> ' + mqtt.connack_string(rc))

    if rc == 0:
        # Update the global connected variable
        global connected
        connected = True

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic + ' ' + str(msg.payload))   

# Main loop to get the values and publish them to MQTT
async def main_loop():
    timer = 0
    while True:
        dist = distance()
        print ("Distance = %.1f cm" % dist)
        await asyncio.sleep(1)
        timer += 1
        
        if dist <= 5.0:
            print('Take a photo')
            takephoto()
            f=open("/home/pi/project/photo.jpg", "rb")
            fileContent = f.read()
            image = bytearray(fileContent)
            f.close()
            if connected:
                client.publish('devices/' + device_id + '/messages/events/', image, qos=1)
            else:
                await asyncio.sleep(1)
        
        if(timer == 15):
            timer = 0
            if connected:
                pic = ser.read(20)
                print (pic)
                
                msgPIC = pic.decode("utf8").split(" ")
                count = 0
                for i in range(len(msgPIC)):
                    if msgPIC[i].startswith('T'):
                        temperature = msgPIC[i]
                        temp = temperature.split("T")
                        print ("Temperatura: " + temp[1] + " ºC")
                        count += 1
                    if msgPIC[i].startswith('H'):
                        humidity = msgPIC[i]
                        hum = humidity.split("H")
                        print ("Humidade: " + hum[1] + " %")
                        count += 1
                    if count == 2:
                        break
                                
                #pression = msgPIC[2]
                #press = pression.split("P")
                #print ("Pressão: " + press[1] + " Pa")
                client.publish('devices/' + device_id + '/messages/events/', temperature, qos=1)
                await asyncio.sleep(1)
                client.publish('devices/' + device_id + '/messages/events/', humidity, qos=1)
                await asyncio.sleep(1)
                #client.publish('devices/' + device_id + '/messages/events/', pression, qos=1)
            else:
                await asyncio.sleep(1)
            
            #WriteDateTime(18, 6, 18, 0, 10, 33, 20)
            DateTime = { "Year":0, "Month":0, "Day":0, "DayOfWeek":0, "Hour":0, "Minute":0 }
            date = "Date"
            date += ReadDateTime(DateTime)
            print("Date/Time: " + date)

            if connected:
                client.publish('devices/' + device_id + '/messages/events/', date , qos=1)
            else:
                await asyncio.sleep(1)
            
## The MQTT standard ports are blocked at ESTG, so we will use a Websockets-based transport
client = mqtt.Client(client_id=device_id, transport='websockets')
client.on_connect = on_connect
client.on_message = on_message

# Generate the SAS token (valid for 1 h, by default)
sas_token = generate_sas_token(iothub_name + '/devices/' + device_id, SIGN_KEY, 'iothubowner')

# Keep-alive of 60 seconds
client.username_pw_set(username = iothub_name + '/' + device_id + '/api-version=2016-11-14', 
                       password = sas_token)
client.ws_set_options(path='/$iothub/websocket')
client.tls_set(ca_certs=None, certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1, ciphers=None)
client.tls_insecure_set(False)
client.connect(iothub_name, port=443, keepalive=60)

# Start the MQTT network processing (non-blocking) loop and proceed
client.loop_start()

# Main loop
loop.create_task(main_loop())
loop.run_forever()
