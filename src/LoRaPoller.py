from threading import Lock
import threading
import time
import subprocess
import re
import traceback
import os
from . import PrctlTool



class LoRaPoller(threading.Thread):
  def __init__(self, app,radio,sleep = 10):
    threading.Thread.__init__(self,name = 'lorapoller')
    self.radio = radio
    self.lock = Lock()
    self.running = True #setting the thread running to true
    self.sleep = sleep
    self.packet = []
    self.app = app
    self.chans = self.app.LoRa_Ch
       
  
  def run(self):
    PrctlTool.set_title('LoRaPoller')
    try:
      list_of_names = []
      list_of_names.clear()
      while self.running:
        cpu = int(self.radio.get_CPU() * 1000)
        df = int(self.radio.get_df()*100)
        self.radio.add_ai_payload(self.packet,self.chans['df'],df)      
        self.radio.add_ai_payload(self.packet,self.chans['cpu'],cpu)

        #self.app.log("LoRa","Sent Regular LoRa Message")
        
        
        for t in threading.enumerate():
          list_of_names.append(t.name)
          
        if 'airodump' in list_of_names:
              self.radio.add_di_payload(self.packet,self.chans['airodump'],0x01)
        else:
              self.radio.add_di_payload(self.packet,self.chans['airodump'],0x01)
      
        if 'gpspoller' in list_of_names:
              self.radio.add_di_payload(self.packet,self.chans['gpspoller'],0x01)
        else:
              self.radio.add_di_payload(self.packet,self.chans['gpspoller'],0x00)    
              
        if 'menupoller' in list_of_names:
              self.radio.add_di_payload(self.packet,self.chans['menupoller'],0x01)
        else:
              self.radio.add_di_payload(self.packet,self.chans['menupoller'],0x00)

        if 'bluetoothpoller' in list_of_names:
              self.radio.add_di_payload(self.packet,self.chans['bluetoothpoller'],0x01)
        else:
              self.radio.add_di_payload(self.packet,self.chans['bluetoothpoller'],0x00)              
      
        if self.app.gpspoller.has_fix():
              self.radio.add_di_payload(self.packet,self.chans['gpsLock'],0x01)
        else:
              self.radio.add_di_payload(self.packet,self.chans['gpsLock'],0x00)
              
        self.radio.send_pi_data(self.packet)
        self.packet.clear()
        list_of_names.clear()
        self.app.log("LoRa","Sent Message")
        
        time.sleep(self.sleep)
    except Exception as e:
      self.app.log('menu poller has an error: ', e)
      pass
      
          
  def stop(self):
      self.running = False
      return 0