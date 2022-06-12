import threading
import math
from gps import *
import os
from . import PrctlTool

try:
  import RPi.GPIO as GPIO
  GPIO.setmode(GPIO.BCM) 
except:
  print("No gpio")


class GpsPoller(threading.Thread):
  def __init__(self, gpsd, app):
    threading.Thread.__init__(self,name='gpspoller')
    self.gpsd = gpsd
    self.application = app
    self.app = app
    self.date = False
    self.running = True #setting the thread running to true
    self.gpio = 17
    self.epx = 100
    self.epy = 100
    
    try:
      GPIO.setup(self.gpio, GPIO.OUT, initial=GPIO.LOW)
      self.app.cprint("Set GPIO %s low"%self.gpio)
    except:
      pass

  def run(self):
    PrctlTool.set_title('gps poller')
    #self.app.cprint("GPS Poller Log Running")
    while self.running:
      next(self.gpsd) #this will continue to loop and grab EACH set of gpsd info to clear the buffer
      TIMEZ = 10 
      # read in x, y position
      x = float(self.gpsd.fix.epx)
      if math.isnan(x):
        self.app.cprint ("self.epx is NaN")
        self.epx = 92
      else:
        self.epx = x
      y = float(self.gpsd.fix.epy)
      if math.isnan(y):
        self.app.cprint ("self.epy is NaN")
        self.epy =92
      else:
        self.epy = y
        
      if self.gpsd.utc != None and self.gpsd.utc != '' and not self.date:
        self.date = True
        tzhour = int(self.gpsd.utc[11:13])+TIMEZ
        if (tzhour>23):
          tzhour = (int(self.gpsd.utc[11:13])+TIMEZ)-24
        gpstime = self.gpsd.utc[0:4] + self.gpsd.utc[5:7] + self.gpsd.utc[8:10] + ' ' + str(tzhour) + self.gpsd.utc[13:19]
        self.app.log('GPS poller','Setting system time to GPS time')
        os.system('sudo date --set="%s"' % gpstime)
        
      
          
      if self.has_fix():
        #self.application.log("GPS Poller Log","has fix")
        self.epx = float(self.gpsd.fix.epx)
        self.epy = float(self.gpsd.fix.epy)
          
        try:
          GPIO.output(self.gpio, GPIO.HIGH)
          #print ("Setting GPIO High")
        except:
          pass   
        q = 'insert into gps (latitude, longitude) values ("%s", "%s")'%(self.gpsd.fix.latitude, self.gpsd.fix.longitude)
        self.application.query(q)
        
      else:
        try:
          self.app.cprint("GPS Poller NO fix")
          GPIO.output(self.gpio, GPIO.LOW)
          self.app.cprint ("Setting GPIO low due to bad GPS fix")
        except:
          pass
  def getPrecision(self):
    return max(self.epx, self.epy)

  def has_fix(self, accurate = True):
    fix = int(self.gpsd.fix.mode) 
    self.app.cprint ("GPS FIX MODE %s"%fix)
    if (fix <= 1):
      self.app.cprint("Returning GPS Fix False")
      return False
    if( accurate ):
      self.app.cprint("Fix mode ok")
      self.app.cprint ("GPS epx %s looking for %s i think it is %s"%(self.gpsd.fix.epx,self.application.args.accuracy,self.epx))
      self.app.cprint ("GPS epy %s looking for %s I think it is %s"%(self.gpsd.fix.epy,self.application.args.accuracy,self.epy))
      
      if self.epx <= float(self.application.args.accuracy) and self.epy <= float(self.application.args.accuracy):
        fix = True
      else:
        fix = False  
    self.app.cprint("returning GPS FIX: %s"%fix)
    return fix
  
  def stop(self):
      GPIO.output(self.gpio, GPIO.LOW)
      self.app.cprint("Set GPIO %s low"%self.gpio)
      self.running = False 
