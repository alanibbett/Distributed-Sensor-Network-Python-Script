from threading import Lock
import threading
import time
import subprocess
import re
import traceback
from . import PrctlTool
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)	
import pdb
import sys
sys.path.append("./src/oledmenus")
sys.path.append("./src/oledmenus/menusystem")
# menusystem global setting file
import globalsettings
# import menu system project files
# import functions for menufunc handlers
from myFunctions import *
# import graphics class
from displayClass import *
# import button handler class
from buttonClass import *
# import menu handler classes
from menuHandlerClass import *
# import menu system class
from menuSystemClass import *
# import extended classes
from myClasses import *





class MenuPoller(threading.Thread):
  def __init__(self, app):
    threading.Thread.__init__(self,name='menupoller')
    self.application = app
    self.lock = Lock()
    self.menusystem = MenuSystem() # create out menu system
    self.running = True #setting the thread running to true
    self.sleep = 1
    self.radio = self.application.radio
    globalsettings.RADIO = self.radio
    globalsettings.APPLICATION = self.application
  
  def run(self):
    PrctlTool.set_title('menupoller')
    try:
      while self.running:
        pos = self.application.getPosition()
        #fix = pos is not None
        #if fix:
          #lon, lat, source = pos
        gpsLockMode = self.application.gpspoller.gpsd.fix.mode
        globalsettings.GPS_MODE = gpsLockMode
        globalsettings.GPS_ACCURACY = self.application.args.accuracy 
        globalsettings.GPS_ESTX = self.application.gpspoller.gpsd.fix.epx
        globalsettings.GPS_ESTY = self.application.gpspoller.gpsd.fix.epy
      
        
        self.menusystem.checkButtons()
        self.menusystem.checkScreenSaver()        
        self.menusystem.updateScreen()
        
        #time.sleep(self.sleep)
    except Exception as e:
      self.application.log('menu', e)
      
          
  def stop(self):
      self.running = False
      GPIO.cleanup()
      return 0