import RPi.GPIO as GPIO # use RPi library for controlling GPIO pins
import time
import math
import logging
import os, sys
   
# modules for controlling components
import modules.Tb6612fngControl as Tb6612fng
import modules.PwmControl as PwmControl
import modules.RGBLEDControl as RGB
from gpiozero import DistanceSensor

from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import AngularServo

# modules for camera vision 
import cv2
from PIL import Image
from picamera2 import Picamera2

GPIO.setwarnings(False) # turn off warnings for pins (if pins were previously used and not released properly there will be warnings)
GPIO.setmode(GPIO.BOARD) # pin name convention used is pin numbers on board

WHEELBASE = 0.12

picam2 = Picamera2()
picam2.preview_configuration.main.size=(1920,1000)
picam2.preview_configuration.main.format = 'RGB888'
picam2.start()

# initialise components 
factory = PiGPIOFactory()
servo = AngularServo(5, min_angle=-90, max_angle=90, min_pulse_width=0.0004, max_pulse_width=0.0026, pin_factory=factory)
 
car = Tb6612fng.motor(stby=37, pwmA=35, ai1=36, ai2=40) 
LED = RGB.LED(red=8, blue=12, green=10) 

us2 = DistanceSensor(echo=27, trigger=22, max_distance=3) #pins are gpio pins
us3 = DistanceSensor(echo=10, trigger=9, max_distance=3) #pins are gpio pins
us4 = DistanceSensor(echo=6, trigger=13, max_distance=3) #pins are gpio pins

class trafficSign:

    minWidth = 30
    minHeight = 30

    X = 0
    Y = 0

    def __init__(self, bgr, lowerLimit, upperLimit, minDist):
        self.bgr = bgr
        self.height, self.width = 0, 0
        self.minDist = minDist
        self.dist = 0

        mask = cv2.inRange(hsvImage, lowerLimit, upperLimit) #create an image with only the colour inside
        mask_ = Image.fromarray(mask) #convert to Image object so that we can use the library to get bounding box
        self.bbox = mask_.getbbox() #get bounding box


    def printBbox(self):
        if self.bbox is not None:
            x1, y1, x2, y2 = self.bbox

            self.height, self.width = abs(y2-y1), abs(x2-x1)

            if self.height > trafficSign.minHeight and self.width > trafficSign.minWidth:
                self.X, self.Y = (x1+x2)/2, (y1+y2)/2 #get X,Y of Bbox middle

                cv2.rectangle(frame, (x1, y1), (x2, y2), self.bgr, 5) #print bounding box onto frame

                #print("distance = ", (frame.shape[0]/self.height)*self.minDist) #print distance of object to camera
                self.dist = int((frame.shape[0]/self.height)*self.minDist)

def turn(radius, direction):

    angle = math.degrees(math.asin(WHEELBASE/radius))

    # print(angle)

    if (direction == "left"):
        servo.angle = angle - 7
        # servo.write(90 + angle)
    elif (direction == "right"):
        servo.angle = -angle - 7
        # servo.write(90 - angle)

done = 0

while True:

    capture = picam2.capture_array()

    global frame
    global hsvImage

    frame = capture
    frame = cv2.flip(frame, 0) # use 0 to flip vertically
    frame = cv2.flip(frame, 1) # use 1 to flip horizontally
    hsvImage = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)   #convert image from bgr to hsv

    #create trafficSign objects
    green = trafficSign((0,255,0), (40, 100, 100), (70, 255, 255), 8)
    red = trafficSign((0,0,255), (0, 200, 130), (5, 255, 255), 8)

    #print bounding box for trafficSign on the video frames
    green.printBbox()
    red.printBbox()

    #shape[1] ==> width = 640,   shape[0] ==> height = 480
    cv2.line(frame, (frame.shape[1]//2, 0), (frame.shape[1]//2, frame.shape[0]), (0, 255, 255), thickness = 3) #centre line
    cv2.putText(frame, "Dist: " + str(green.dist), (frame.shape[1] - 120, 440), cv2.FONT_HERSHEY_TRIPLEX, 1.0, (0, 255, 0), 1)
    cv2.putText(frame, "Dist: " + str(red.dist), (20, 440), cv2.FONT_HERSHEY_TRIPLEX, 1.0, (0, 0, 255), 1)

    cv2.imshow('Camera', frame)  #show video   

    # main code 
    # -------------------------------------------------------------------------------------------------------------

    # Get distances in cm
    frontDist = us4.distance*100 
    leftDist = us2.distance*100
    rightDist = us3.distance*100

    if frontDist <= 70 and done == 0:
        done = 1

        if leftDist < rightDist : 
            LED.rgb(255,255,0) #yellow
            turn(0.2, "right") 
            logging.info(('Turning right'))
        else:
            LED.rgb(255,0,255) #purple'Front: ' + fron
            turn(0.2, "left")
            logging.info(('Turning left'))

        car.speed(20)   
        time.sleep(2)

    else:
        LED.off() 
        servo.angle = 0 - 7
        car.speed(30) 
        logging.info(f'front: {frontDist} left: {leftDist} right: {rightDist}')

    if frontDist >= 100:
        done = 0


    if cv2.waitKey(1) & 0xFF == ord('q'): #break out of loop if 'q' is pressed
        GPIO.cleanup() # must include at the end of the program to release the pins used
        break

cv2.destroyAllWindows()