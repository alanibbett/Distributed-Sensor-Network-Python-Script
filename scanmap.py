#!/usr/bin/env python
debug = False

import subprocess
import threading
from threading import Lock
import time
from gps import *
import os
import sys
from os import path
import subprocess
import argparse
import re
import sqlite3
from threading import Thread
from math import radians, cos, sin, asin, sqrt, floor
import hashlib

import datetime
import traceback

from src.GpsPoller import *
from src.AirodumpPoller import *
from src.BluetoothPoller import *
from src.Synchronizer import *
from src.WebUi import *
from src.DnsServer import *
from src.MenuPoller import *
from src.LoRa import *
from src.LoRaPoller import *


#meters
min_gpsd_accuracy = 30

try:
  import RPi.GPIO as GPIO
  GPIO.setmode(GPIO.BCM)
  GPIO.setwarnings(False) #turn off warnings about gpio channel in use
  
except:
  print("No gpio")

USE_SCAPY=False

if(USE_SCAPY):
  from scapy.all import *
  from scapy_ex import *
else:
  import csv
  
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interface", help="wifi interface")    
    parser.add_argument("-s", "--sleep", help="Sleep time in seconds")  
    parser.add_argument('-x', '--anonymize', action='store_true', help='anonymize last 3 bytes of bssid')
    parser.add_argument("-d", "--database", help="wifi database")
    parser.add_argument("-n", "--dns", action='store_true', help="dns name server for dns data exfiltration")
    parser.add_argument('-w', '--www', help='www port')
    parser.add_argument('-p', '--position', help='lat,lon position')
    parser.add_argument('-l', '--log', action='store_true', help='lat,lon position')
    parser.add_argument('-a', '--accuracy', help='minimum accuracy')
    parser.add_argument('-u', '--synchro', help='synchro uri ie http://test.com:8686')
    parser.add_argument('-e', '--enable', action='store_true', help='enable db synchro through json')
    parser.add_argument('-m', '--monitor', action='store_true', help='use monitor mode instead of iwlist')
    parser.add_argument('-b', '--bssid', help='ignore bssid', action='append', nargs='*')
    parser.add_argument('-c', '--esp', help='force esp position hostname0:lat:lon,hostname1:lat,lon,')
    parser.add_argument('-f', '--fault', help='print fault finding logs on the console')
    return parser.parse_args()

      
class Application (threading.Thread):
    def __init__(self, args):
        threading.Thread.__init__(self,name='scanmap')
        self.args = args
        self.manufacturers_db = '/usr/share/wireshark/manuf'
        self.cache = {
            'history':{}
          }
        self.version = self.get_version()
        self.manufacturers = {}
        self.lock = Lock()
        self.stopped = False
        self.session = gps(mode=WATCH_ENABLE)
        self.ignore_bssid = []
        self.interface = ''
        self.radio = lora_radio()
        self.airodump = None
        self.dns = None
        self.wifiPosition = None
        self.bluePoller = BluetoothPoller(self)
        self.menupoller = MenuPoller(self)
        self.updates_count = {'wifis':0, 'probes':0, 'stations':0, 'bt_stations':0}
        self.led = 17
        GPIO.setup(self.led, GPIO.OUT, initial=GPIO.LOW)
        self.flashLED()
        self.LoRa_Ch = {
              "appStart": 0x01,
              "appReboot": 0x02,
              "appShutdown": 0x03,
              "gpsLock": 0x04,
              "gpspoller":0x05,
              "bluetoothpoller":0x06,
              "airodump":0x07,
              "menupoller":0x08,
              "reboot":20,
              "shutdown":21,
              "df":40,
              "cpu":41
              }
        
        
        self.radio.update_status(self.LoRa_Ch['appStart'],1,1)
        self.clear_LoRa_console()
        self.log("LoRa","Set App Start Message")
        
        
        if debug == True:
          self.flog = True
        else:
          self.flog = False

        
        
        if self.args.fault:
          self.flog = False
      
          
          
        if self.args.dns:
          self.dns = DnsServer(self)
          self.dns.start()
        
        if self.args.position is not None:
          lat, lon = self.args.position.split(',')
          self.args.position = (float(lat), float(lon))
        
        if(self.args.accuracy is None):
          self.args.accuracy = min_gpsd_accuracy
        
        if(self.args.database is not None):
            db = self.args.database
        else:
            db = "./wifimap.db"
        self.db = sqlite3.connect(db, check_same_thread=False)
        def to_text(text):
          try:
            text.decode('utf-8')
            return text
          except:
            self.log('sqlite', 'encoding error '+text)
            return 'encoding_error'
        self.db.text_factory = to_text
        self.query_db = self.db.cursor()
        
        try:
            self.query('''select * from wifis''')
    
        except:
          
            self.createDatabase()
            self.log("Database","Created")
            

              
        self.LoRapoller = LoRaPoller( self,self.radio,60)
        self.LoRapoller.start()
        self.log("LoRa Poller","Started")
        
        self.gpspoller = GpsPoller(self.session, self)
        self.gpspoller.start()
        self.log("GPS Poller","Started")
        
        self.menupoller.start()
        self.log("MenuPoller","Started")
        
        self.bluePoller.start()
        self.log("Bluetooth Poller","Started")
        
        for b in self.getConfig('bssid').split(','):
          self.ignore_bssid.append(b)
        
        if args.bssid is not None:
          for b in args.bssid:
            self.ignore_bssid.append(b[0].upper())
        
        if not args.enable:
          args.enable = self.getConfig('enable') == 'true'
        
        if args.synchro is None:
          if self.getConfig('synchro') != '':
            args.synchro = self.getConfig('synchro')
        
        self.synchronizer = Synchronizer(self, args.synchro)
        if self.args.esp is not None:
          for esp in self.args.esp.split(','):
            hostname, lat, lon = esp.split(':')
            self.synchronizer.esp8266[hostname] = {}
            self.synchronizer.esp8266[hostname]['position']=(float(lat),float(lon),0)
        
        if args.synchro is not None:
          self.synchronizer.start()
          pass
        
        try:
          if self.args.interface is not None:
              self.interface = self.args.interface
          else:
              self.interface = self.getWirelessInterfacesList()[0]
              
          self.ignore_bssid.append(self.getMacFromIface(self.interface).upper())
        except:
          self.log("App", "No wifi interface so no action")
          
        # this next bit fires up the interface mon0 into monitoring mode
        
        if self.args.monitor:
          if self.interface != 'mon0':
            if 'mon0' not in self.getWirelessInterfacesList():
              #cmd = ['airmon-ng', 'start' ,self.interface]
              self.log("WiFi","Enabling Monitor Mode")
              cmd = ["sudo","iw","phy", "phy0", "interface", "add","mon0", "type","monitor"] 
              p = subprocess.run(cmd)
              self.log("WiFi","Bringing int up")
              cmd = ['sudo','ifconfig','mon0','up'] 
              p = subprocess.Popen(cmd)
              p.wait()
              
              
          self.interface = 'mon0'
                
        
      
        if self.args.www is not None:
            port = int(self.args.www)
        else:
          if self.getConfig('www') != '':
            port = int(self.getConfig('www'))
          else:
            port = 8686
        self.loadManufacturers()
        try:
          self.httpd = WebuiHTTPServer(("", port),self, WebuiHTTPHandler)
          self.httpd.start()
          self.log("http","Started")
          self.log("Port",port)
        except :
    
          self.log("http", "web hmi not available")
    
    def get_version(self):
      try:
        cmd = ['git', 'describe', '--always']
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()
        (stdoutdata, stderrdata) = process.communicate();
        return stdoutdata
      except:
        return 'unknown'
    
    def query(self, query):
      with self.lock:
        self.query_db.execute(query)
    
    def fetchone(self, query):
      with self.lock:
        self.query_db.execute(query)
        return self.query_db.fetchone()
    
    def fetchall(self, query):
      with self.lock:
        self.query_db.execute(query)
        return self.query_db.fetchall()
    
    def getConfig(self, _key):
      try:
        q = '''select value from config where key == "%s"'''%_key
        res = self.query.fetchone(q)
        return res[0]
      except:
        return ''
    
    def packet_handler(self, pkt):
      if pkt.haslayer(Dot11):
        if pkt.type == 0 and pkt.subtype == 8:
          rssi =0
          print("==> %s %s %s"%(rssi, pkt.addr2, pkt.info))
          pkt.show()
    
    def getStats(self, full = False):
      stat = {'wifis': {}, 'stations':{}, 'bt_stations':{}, 'probes':{}}
      q = '''select count(*) from wifis where encryption == 0'''
      try:
        stat['wifis']['open'] = self.fetchone(q)[0]
      except:
        stat['wifis']['open'] = 0
      
      q = '''select count(*) from wifis'''
      stat['wifis']['all'] = self.fetchone(q)[0]
      
      if full:
        q = '''select essid, count(*) as count_essid from wifis group by essid order by count_essid desc limit 20'''
        stat['wifis']['top'] = self.fetchall(q)
        
        q = '''select count(*) as count_manuf, substr(bssid,0,9) as manufacturer from wifis group by manufacturer order by count_manuf desc limit 20'''
        stat['wifis']['manufacturer'] = []
        for m in self.fetchall(q):
          stat['wifis']['manufacturer'].append({
            'count':  m[0],
            'manufacturer': self.getManufacturer(m[1])
            })
        
        q = '''select essid, count(*) as count_essid from probes group by essid order by count_essid desc limit 20'''
        stat['probes']['top'] = self.fetchall(q)
        
        q = '''select count(distinct bssid) from stations'''
        stat['stations']['all'] = self.fetchone(q)[0]
        
        q = '''select count(distinct bssid) from bt_stations'''
        stat['bt_stations']['all'] = self.fetchone(q)[0]
        
        q= '''select (class >> 8 & 0x1F) as class_, count(DISTINCT bssid) as cl from bt_stations group by class_ order by cl desc;'''
        res = self.fetchall(q)
        classes = []
        for i in res:
          classes.append({
            'class_description': self.bluePoller.get_major_device_description(i[0]),
            'count': i[1]
            
            })
        stat['bt_stations']['class'] = classes
        
        q = '''select channel, count(*) as chan from wifis group by channel order by chan desc'''
        stat['wifis']['channels'] = self.fetchall(q)
      
      q = '''select count(distinct essid) from probes'''
      stat['probes']['all'] = self.fetchone(q)[0]
      return stat
    
    def getLastUpdate(self):
        q = '''select date from wifis order by date desc limit 1'''
        return self.fetchone(q)
    
    def getUsersDns(self,bssid):
      q='select * from users_dns where bssid = "%s"'%bssid
      dns = []
      try:
        res = self.fetchall(q)
        for r in res:
          dns.append({
            'bssid':r[0],
            'host':r[1],
            'date':r[2],
            })
      except:
        pass
      return dns
    
    def getWifisFromEssid(self, essid):
      where = ''
      if isinstance(essid, str):
        where = 'essid="%s"'%essid 
      else:
        where = 'essid in ("%s")'%','.join(essid)
      
      q='select * from wifis where %s'%where
      return self.fetchall(q)
      
    
    def getStationsPerDay(self, bssid = None, limit = 0):
      limit_str = ''
      if limit != 0:
        limit_str = 'LIMIT %s'%limit
      where_bssid = ""
      if bssid is not None:
        where_bssid = ' where bssid = "%s"'%bssid

      q='''select bssid, date(date), count(*) from stations %s group by date(date) order by count(distinct date(date)) DESC, date %s'''%(where_bssid, limit_str)
      res = self.fetchall(q)
      if len(res) == 0:
        q='''select bssid, date(date), count(*) from bt_stations %s group by date(date) order by count(distinct date(date)) DESC, date %s'''%(where_bssid, limit_str)
        res = self.fetchall(q)
      return res
    
    def getAllStations(self, search = None):
      stations = []
      search_where = ""
      if search is not None:
        search_where = "where %s"%search
      
      q = 'select * from stations %s'%search_where
      res = self.fetchall(q)
      if res is not None:
        for s in res:
          station = {}
          station['bssid'] = s[1]
          station['latitude'] = s[2]
          station['longitude'] = s[3]
          station['signal'] = s[4]
          station['date'] = s[5]
          station['manufacturer'] = self.getManufacturer(station['bssid'])
          stations.append(station)
        
      return stations
    
    def getAllBtStationsByClass(self, _class):
       q = '''select * from bt_stations where (class >> 8 & 0x1F)=%s'''%_class
       return self.fetchall(q)
    
    def getAllBtStations(self, search):
      stations = []
      search_where = ""
      if search is not None:
        search_where = "where %s"%search
      
      q = 'select * from bt_stations %s'%search_where
      res = self.fetchall(q)
      if res is not None:
        for s in res:
          station = {}
          station['bssid'] = s[1]
          station['class'] = s[2]
          station['class_description'] = self.bluePoller.get_major_device_description(self.bluePoller.parse_class(station['class']))
          station['name'] = s[3].replace('\\','')
          station['latitude'] = s[4]
          station['longitude'] = s[5]
          station['date'] = s[6]
          station['manufacturer'] = self.getManufacturer(station['bssid'])
          stations.append(station)
        
      return stations

    def getDevices(self):
      devices = []      
      q = 'select * from devices group by hostname order by date desc'
      res = self.fetchall(q)
      if res is not None:
        for d in res:
          device = {}
          device['hostname'] = d[0]
          device['latitude'] = d[1]
          device['longitude'] = d[2]
          device['source'] = d[3]
          device['date'] = d[4]
          devices.append(device)
        
      return devices
    
    def getSyncProbes(self, date = None):
      date_where = ''
      if date is not None:
        date_where = 'where date >= "%s"'%date

      q = 'select * from probes %s order by date asc'%date_where
      res = self.fetchall(q)
      probes = []
      for p in res:
        probes.append({
         'bssid': p[0],
         'essid': p[1].replace('\\',''),
         'date': p[2],
        }) 
      return probes

    def getAllProbes(self, distinct = False, essid = None, date = None):
      essid_where = ""
      date_where = ""
      if essid is not None:
        essid_where = 'where essid = "%s"'%essid
      if date is not None:
        date_where = 'where date >= "%s"'%date
      if not distinct:
        q = 'select * from probes %s %s order by essid'%(essid_where, date_where)
        res = self.fetchall(q)
        probes = []
        for p in res:
          probes.append({
            'bssid': p[0],
            'essid': p[1].replace('\\',''),
            'date': p[2],
            'manufacturer': self.getManufacturer(p[0])
            })
        return probes
      else:
        q = 'select P.essid, count(*) as probes_count, (select count(*) from wifis W where W.essid = P.essid) as wifis_count from probes P %s %s group by P.essid order by probes_count desc, wifis_count desc'%(essid_where, date_where)
        return self.fetchall(q)
    
    def getAll(self,p0 =None, p1=None,  date = None):
        wifis = {}
        where = ''
        date_where = ''
        if date is not None:
          where = 'where'
          date_where = 'date > "%s"'%date
        if p0 is not None:
          where = 'where'
          location_where = 'latitude > %s and longitude > %s and latitude < %s and longitude < %s'%(p0[0], p0[1], p1[0], p1[1])
          
        q = 'select * from wifis %s %s %s order by latitude, longitude'%(where, location_where, date_where)
        # should create an object replace('\\','')
        wifis["networks"] = self.fetchall(q)
        
        q = 'select avg(latitude), avg(longitude) from wifis %s group by date order by date desc limit 1'%date_where
        wifis["center"] = self.fetchone(q)
        wifis["stat"] = self.getStats()
        return wifis
    
    def getLast(self):
        wifis = {}
        q = '''select * from wifis order by date desc, latitude, longitude limit 10'''
        wifis["networks"] = self.fetchall(q)
        wifis["stat"] = self.getStats()
        return wifis
    
    def getCurrent(self):
      wifis = self.scanForWifiNetworks()
      probes = []
      stations = []
      bt_stations = []
      
      if self.args.monitor and not USE_SCAPY:
        probes = self.airodump.probes
        st = self.airodump.stations
        for s in st:
          if s['bssid'] not in self.cache['history']:
            self.cache['history'][s['bssid']] = self.getStationsPerDay(s['bssid'])
          s['history'] = self.cache['history'][s['bssid']]
          stations.append(s)
          
      for s in self.bluePoller.stations:
        if s['bssid'] not in self.cache['history']:
          self.cache['history'][s['bssid']] = self.getStationsPerDay(s['bssid'])
        s['history'] = self.cache['history'][s['bssid']]
        bt_stations.append(s)
          
      data = {}
      data['wifis'] = wifis
      data['probes'] = probes
      data['stations'] = stations
      data['bluetooth'] = bt_stations
      return data
    
    def getStation(self, bssid):
      station = {
        'traces': [],
        'probes': [],
        'wifis': [],
        'manufacturer': self.getManufacturer(bssid),
        }
      q = '''select * from stations where bssid = "%s"'''%bssid
      traces = self.fetchall(q)
      if traces == []:
        q = '''select * from bt_stations where bssid = "%s"'''%bssid
        traces = self.fetchall(q)
        for t in traces:
          station['traces'].append({
            'bssid' : t[1],
            'class' : t[2],
            'name' : t[3],
            'latitude' : t[4],
            'longitude' : t[5],
            'date' : t[6]
            })
      else:
        for t in traces:
          station['traces'].append({
            'bssid' : t[1],
            'latitude' : t[2],
            'longitude' : t[3],
            'signal' : t[4],
            'date' : t[5]
            })
      q = '''select * from probes where bssid = "%s"'''%bssid
      
      probes = self.fetchall(q)
      search = []
      for p in probes:
        station['probes'].append(p[1])
        search.append('"%s"'%p[1])
        
      q = '''select * from wifis where essid in (%s)'''%','.join(search)
      wifis = []
      
      for n in self.fetchall(q):
        network = {}
        network['bssid'] = n[0]
        network['essid'] = n[1]
        network['encryption'] = n[2]
        network['signal'] = n[3]
        network['longitude'] = n[4]
        network['latitude'] = n[5]
        network['frequency'] = n[6]
        network['channel'] = n[7]
        network['mode'] = n[8]
        network['date'] = n[9]
        wifis.append(network)
      
      station['wifis'] = wifis
      
      station['days'] = self.getStationsPerDay(bssid)
      station['users_dns'] = self.getUsersDns(bssid)
      
      return station
    
    def createDatabase(self):
        print("initiallize db")
        self.query('''CREATE TABLE wifis
            (bssid text, essid text, encryption bool, signal real, longitude real, latitude real, frequency real, channel int, mode text, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, gps boolean)''')
        self.query('''CREATE TABLE config
            (key text, value text)''')
        self.query('''CREATE TABLE gps
            (latitude real, longitude real, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        self.query('''CREATE TABLE stations
            (id integer primary key, bssid  text, latitude real, longitude real, signal real, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        self.query('''CREATE TABLE bt_stations
            (id integer primary key, bssid  text, class integer, name text, latitude real, longitude real, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        self.query('''CREATE TABLE probes (bssid  text, essid text, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        self.query('''CREATE TABLE sync (hostname  text, entity text, date TIMESTAMP)''')
        self.query('''CREATE TABLE devices (hostname  text, latitude real, longitude real, source text, date TIMESTAMP)''')
        
        self.query('''CREATE TABLE users_dns
        (bssid text, host text, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        self.query('''CREATE TABLE users_password
        (bssid text, login text, password text, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    def log(self, name, value):
      
      print("%s   %s : %s"%(datetime.datetime.now(), name, value))
        
    def cprint(self, value):
      if self.flog == True:
        print("%s"%value)
        
    
    def stop(self):
        self.stopped = True
        try: 
          GPIO.cleanup()
        except:
          pass
        if self.LoRapoller.running:
            self.LoRapoller.stop()
            self.LoRapoller.join()
            self.log("LoRa Poller","Stopped")
        if self.gpspoller.running:
            self.gpspoller.stop()
            self.gpspoller.join()
            self.log("GPS","Stopped")
        else:
            self.log("GPS","Not running so no stop.")
        if self.synchronizer.running:
            self.synchronizer.stop()
            self.synchronizer.join()
            self.log("Sync","Stopped")
        else:
            self.log("Sync","Not running so no stop.")
            
        self.httpd.stop()
        self.httpd.join()
        self.log("httpd","Stopped")
        
        if self.airodump.running:
            self.airodump.stop()
            self.airodump.join()
            self.log("airodump","Stopped")
        else:
            self.log("airodump","Not running so no stop.") 
        if self.bluePoller.running:
            self.bluePoller.stop()
            self.bluePoller.join()
            self.log("Bluetooth","Stopped")
        else:
            self.log("Bluetooth","Not running so no stop.")
    
    def has_fix(self, accurate = True):
      return self.gpspoller.has_fix(accurate)
    
    def run(self):
        self.log("main loop","Begining")
        if self.interface == '':
          self.log("wifi", "no interface - nothing will happen")
          while not self.stopped:
            time.sleep(1)
          return
        
        if self.args.monitor:
          if USE_SCAPY:
            sniff(iface=self.interface, prn = self.packet_handler)
            pass
          else:
            self.airodump = AirodumpPoller(self)
            self.airodump.start()
            pass
        
        while not self.stopped:
          try:
            
            
            wifis = self.scanForWifiNetworks()
            updated = 0
            self.cprint("networks found %s"%(len(wifis)))
            for w in wifis:
              try:
                if self.update(w):
                    updated += 1
                    
              except:
                self.log("wifi", "insert fails")
                print(w)
                
            if updated != 0:
                self.log("updated wifi", updated)
                self.updates_count['wifis'] += updated
            
            self.wifiPosition = self.getWifiPosition(wifis)
            
            
            
            if self.args.monitor and not USE_SCAPY:
              try:
                updated = 0
                for p in self.airodump.probes:
                  if self.update_probe(p):
                    updated += 1
                  if updated != 0:
                    self.log("updated probes", updated)
                    self.updates_count['probes'] += updated
              except:
                self.log("wifi", "probes insert fails")
              
              try:
                updated = 0
                for s in self.airodump.stations:
                  if self.update_station(s):
                    updated += 1
                
                if updated != 0:
                    self.log("updated stations", updated)
                    self.updates_count['stations'] += updated
              except:
                self.log("wifi", "stations insert fails")
            
            
            bt = self.bluePoller.stations
            updated = 0
            for b in bt:
              try:
                if self.update_bt_station(b):
                    updated += 1
              except:
                self.log("bluetooth", "insert fails")
                print(b)
                
            if updated != 0:
                self.log("updated bluetooth", updated)
                self.updates_count['bt_stations'] += updated
            
            
            self.commit()
          except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.log("wifi exception", e)
            traceback.print_exception(exc_type,exc_value,exc_traceback)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print((exc_type, fname, exc_tb.tb_lineno))
            
          if self.args.sleep is not None:
              sleep = int(self.args.sleep)
          else:
              sleep = 2
          time.sleep(sleep)
      
    def commit(self):
      with self.lock:
        try:
          #self.log("DB", 'Attempting Commit')
          self.db.commit()
        except:
          self.log("DB", 'Commit unavailable')
    
    def anonymize_bssid(self, bssid):
      if self.args.anonymize:
        b = bssid.split(':')
        b0 = b[:3]
        b1 = b[3:]
        return '%s:%s'%(':'.join(b0),hashlib.sha256(':'.join(b1)).hexdigest())
      return bssid
    
    def update_dns(self,dns):
      dns['bssid'] = self.anonymize_bssid(dns['bssid'].upper())
      
      q = '''select * from users_dns where bssid="%s" and host="%s"'''%(self.dns["bssid"], dns["host"])
      res = self.fetchone(q)
      if res is None:
        q = '''insert into users_dns (bssid, host) values ("%s","%s")'''%(dns["bssid"], dns["host"])
        try:
          self.query(q)
          return True
        except:
          print("sqlError: %s"%q)
          return False
    
    def update_bt_station(self, station):
      if 'latitude' not in station:
        return False
      station['bssid'] = self.anonymize_bssid(station['bssid'])
      q = '''select * from bt_stations where bssid="%s" and latitude="%s" and longitude="%s" and (julianday('now') - julianday(date))*24 < 2'''%(station["bssid"], station["latitude"], station["longitude"])
      res = self.fetchone(q)
      if res is None:
        q = '''insert into bt_stations (id, bssid, class, name, latitude, longitude) values (NULL, "%s", "%s", "%s", "%s", "%s")'''%(station["bssid"], station['class'], station['name'], station["latitude"], station["longitude"])
        self.query(q)
        return True
      return False
    
    def delete(self, bssid, essid = None):
      if essid is not None:
        q = 'delete from wifis where bssid = "%s" and essid == "%s"'%(bssid,essid)
      else:
        q = 'delete from wifis where bssid = "%s"'%bssid
      self.query(q)
      q = 'delete from stations where bssid = "%s"'%bssid
      self.query(q)
      q = 'delete from bt_stations where bssid = "%s"'%bssid
      self.query(q)
      
    def update(self, wifi):
        if  wifi['essid'] == 'encoding_error':
          #print("essid encoding error")
          return False
        if 'latitude' not in wifi:
          #print("Latitude not avail")
          return False
        if math.isnan(wifi["longitude"]):
            #print("Latitude nan")
            return False
                
        date_str = 'CURRENT_TIMESTAMP'
        if('date' in wifi):
          date_str = '"%s"'%wifi['date']
        
        wifi['bssid'] = self.anonymize_bssid(wifi['bssid'])
        q = '''select * from wifis where bssid="%s" and ( essid="%s" or bssid == "" )'''%(wifi["bssid"], wifi["essid"])
        #print ("query sent : %s"%(q))
        res = self.fetchone(q)
        if res is None:
            gps = 0
            if wifi["gps"]:
              gps = 1
              
            q = 'insert into wifis (bssid, essid, encryption, signal, longitude, latitude, frequency, channel, mode, date, gps) values ("%s", "%s", %s, %s, %s, %s, %s, %s, "%s", %s, %s)'%(wifi["bssid"], wifi["essid"], int(wifi["encryption"]), wifi["signal"], wifi["longitude"], wifi["latitude"], wifi["frequency"], wifi["channel"], wifi["mode"], date_str, gps)
            try:
              self.query(q)
              return True
            except:
              print("sqlError: %s"%q)
              return False
        else:
            try:
              signal = res[3]
              gps = res[10]
              where_source = ""
              gps = 1
              if not gps:
                gps = 0
                where_source = ' and gps = 0 ' 
              q = 'update wifis set bssid="%s", essid="%s", encryption=%s, signal=%s, longitude=%s, latitude=%s, frequency=%s, channel=%s, mode="%s", gps="%s", date=%s where bssid="%s" and essid="%s" %s'%(wifi["bssid"], wifi["essid"], int(wifi["encryption"]), wifi["signal"], wifi["longitude"], wifi["latitude"], wifi["frequency"], wifi["channel"], wifi["mode"], gps, date_str, wifi["bssid"], wifi["essid"], where_source)
              if wifi["signal"] < signal:
                  self.query(q)
                  return True
            except:
              print("sqlError: %s"%q)
        return False
    
    def update_probe(self, probe):
      if  probe['essid'] == 'encoding_error':
        return False
      probe['bssid'] = self.anonymize_bssid(probe['bssid'])
      q = '''select * from probes where bssid="%s" and essid="%s"'''%(probe["bssid"], probe["essid"])
      res = self.fetchone(q)
      if res is None:
        date_str = 'CURRENT_TIMESTAMP'
        if('date' in probe):
          date_str = '"%s"'%probe['date']
        q = '''insert into probes (bssid, essid, date) values ("%s", "%s", %s)'''%(probe["bssid"], probe["essid"], date_str)
        self.query(q)
        return True
      return False

    def update_station(self, station):
      if 'latitude' not in station:
        return False
      station['bssid'] = self.anonymize_bssid(station['bssid'])
      q = '''select * from stations where bssid="%s" and latitude="%s" and longitude="%s" and signal=%s and (julianday('now') - julianday(date))*24 < 2 '''%(station["bssid"], station["latitude"], station["longitude"], station["signal"])
      res = self.fetchone(q)
      if res is None:
        q = '''insert into stations (id, bssid, latitude, longitude, signal) values (NULL, "%s", "%s", "%s", "%s")'''%(station["bssid"], station["latitude"], station["longitude"], station["signal"])
        self.query(q)
        return True
      return False
    
    def loadManufacturers(self):
      
      try:
        manuf = open(self.manufacturers_db,'r').read()
        res = re.findall("(..:..:..)\s(.*)\s#\s(.*)", manuf)
        if res is not None:
          for m in res:
            self.manufacturers[m[0]] = m[1].strip()
      except:
        print("Load manufact Failed")
        pass
      return ''
    
    
    def getManufacturer(self,_bssid):
      try:
        # keep only 3 first bytes
        signature = ':'.join(_bssid.split(":")[:3])
        #print ("manufacturer {0}".format(self.manufacturers[signature.upper()]))
        return self.manufacturers[signature.upper()]
      except:
        pass
      return ''
    
    def scanForWifiNetworks(self):
        if self.args.monitor:
          return self.airodump.getNetworks()
        else:
          networkInterface = self.interface
          output = ""
          if(networkInterface!=None):		
              command = ["iwlist", networkInterface, "scanning"]
              process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
              process.wait()
              (stdoutdata, stderrdata) = process.communicate();
              output =  stdoutdata.decode("utf-8")
              return self.parseIwlistOutput(output)
    
    def parseIwlistOutput(self, data):
        networks = {}
        res = re.findall("Address: (.*)", data)
        if res is not None:
            networks["bssid"] = res
        
        res = re.findall("ESSID:\"(.*)\"", data)
        if res is not None:
            networks["essid"] = res
    
        res = re.findall("Mode:(.*)", data)
        if res is not None:
            networks["mode"] = res
            
        res = re.findall("Channel:(\d*)", data)
        if res is not None:
            networks["channel"] = res
            
        res = re.findall("Frequency:(.*) GHz", data)
        if res is not None:
            networks["frequency"] = res
    
        res = re.findall("Signal level=(.*) dBm", data)
        if res is not None:
            networks["signal"] = res
        
        res = re.findall("Encryption key:(.*)", data)
        if res is not None:
            networks["encryption"] = res
            
        pos = self.getPosition()
        fix = pos is not None
        if fix:
          lon, lat, source = pos
        wifis = []
        print("length of networks list is %s"%len(networks["essid"]))
        
        for i in range(0,len(networks["essid"])):
            n = {}
            print("essid index is %s"%i)
            if fix:
              n["latitude"] = lat
              n["longitude"] = lon
              n['gps'] = source == 'gps'
            n["bssid"] = networks["bssid"][i]
            n["essid"] = networks["essid"][i]
            n["mode"] = networks["mode"][i]
            n["channel"] = networks["channel"][i]
            n["frequency"] = float(networks["frequency"][i])
            n["signal"] = float(networks["signal"][i])
            n["encryption"] = networks["encryption"][i] == "on"
            if n["bssid"] not in self.ignore_bssid:
                wifis.append(n)
        return wifis
        
            
    def getWifiPosition(self, wifis):
      where = []
      if len(wifis) < 3:
        return None
      for n in wifis:
        where.append('( bssid = "%s" and essid = "%s")'%(self.anonymize_bssid(n["bssid"]),n["essid"]))
      q = "select -signal*latitude/-signal, -signal*longitude/-signal from wifis where %s order by latitude asc, longitude asc"%(' or '.join(where))
      res = self.fetchall(q)
      #print("Query sent : %s"%(q))
      if res is not None:
        q = "select * from wifis where %s"%(' or '.join(where))
        used_wifis = []
        for n in self.fetchall(q):
          network = {}
          network['bssid'] = n[0]
          network['essid'] = n[1]
          network['encryption'] = n[2]
          network['signal'] = n[3]
          network['longitude'] = n[4]
          network['latitude'] = n[5]
          network['frequency'] = n[6]
          network['channel'] = n[7]
          network['mode'] = n[8]
          network['date'] = n[9]
          used_wifis.append(network)
        #compute median
        q2_index = int(len(res)/2)
        q1_index = int(q2_index/2)
        q3_index = int(floor(q2_index + q2_index/2))

        intercatile = (res[q3_index][0], res[q3_index][1])
        inferior_limits = (res[q3_index][0] + intercatile[0]*1.5, res[q3_index][1] + intercatile[1]*1.5)
        exterior_limits = (res[q3_index][0] + intercatile[0]*3, res[q3_index][1] + intercatile[1]*3)
        
        q = "select sum(-signal*latitude)/sum(-signal), sum(-signal*longitude)/sum(-signal) from wifis where %s and latitude > %s and longitude > %s and latitude < %s and longitude <%s "%(' or '.join(where), inferior_limits[0], inferior_limits[1], exterior_limits[0], exterior_limits[1] )
        res = self.fetchone(q)
        if res is not None:
          if res[0] is None:
            return None
          return (res[0], res[1], self.haversine(inferior_limits[0], inferior_limits[1], exterior_limits[0], exterior_limits[1]), used_wifis)
        return None
           
    def getPosition(self):
      # Returns Lat and Long and the source of the fix
      # if the fix is GPS then it returns GPS
      # if the fix is WiFi location it returns WiFi
      # if the fix is from the command line it returns cmdline
      if self.args.position is not None:
        return (self.args.position[1], self.args.position[0], 'cmdline')
        #returns cmdline as first choice
      elif self.gpspoller.has_fix():
        longitude = self.session.fix.longitude
        latitude = self.session.fix.latitude
        return (longitude, latitude, 'gps')
        #returns GPS as second choice
      elif self.wifiPosition is not None:
        return (self.wifiPosition[1], self.wifiPosition[0], 'wifi')
        #returns wifi location as third choice 
      return None
       #failing that it returns none.
            
    def getWirelessInterfacesList(self):
        networkInterfaces=[]		
        command = ["iwconfig"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()
        (stdoutdata, stderrdata) = process.communicate();
        output = stdoutdata.decode("utf-8")
        lines = output.splitlines()
        for line in lines:
                if(line.find("IEEE 802.11")!=-1):
                        networkInterfaces.append(line.split()[0])
        return networkInterfaces
    
    def getMacFromIface(self, _iface):
      path = "/sys/class/net/%s/address"%_iface
      data = open(path,'r').read()
      data = data[0:-1] # remove EOL
      return data
    
    def flashLED(self):
      try:
        print("LED Goes on")
        GPIO.output(self.led, GPIO.HIGH) 
        time.sleep(1)
        print("LED Goes off")
        GPIO.output(self.led, GPIO.LOW)
        
      except:
        pass
    
    def haversine(self, lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians 
        lon1, lat1, lon2, lat2 = list(map(radians, [lon1, lat1, lon2, lat2]))

        # haversine formula 
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        r = 6371 # Radius of earth in kilometers. Use 3956 for miles
        return c * r
    
    def clear_LoRa_console(self):
      #clear the LoRa console
      #clear out the status readings on the things network console
      
      self.radio.update_status(self.LoRa_Ch['appReboot'],0x00,0x00)
      self.radio.update_status(self.LoRa_Ch['appShutdown'],0x00,0x00)
      self.radio.update_status(self.LoRa_Ch['gpsLock'],0x00,0x00)
      self.radio.update_status(self.LoRa_Ch['gpspoller'],0x00,0x00)
      self.radio.update_status(self.LoRa_Ch['bluetoothpoller'],0x00,0x00)
      self.radio.update_status(self.LoRa_Ch['airodump'],0x00,0x00)
      self.radio.update_status(self.LoRa_Ch['menupoller'],0x00,0x00)
        
      self.log("LoRa","LoRa Console Cleared")
        
        
        
    def is_mobile(self, manufacturer):
      return manufacturer in ['Apple', 'Nokia', 'Google', "4pMobile", "AavaMobi", "Advanced", "Asmobile", "AutonetM", "AzteqMob", "BejingDa", "Cambridg", "CasioHit", "Cellebri", "CgMobile", "ChinaMob", "CnfMobil", "CustosMo", "DatangMo", "DeltaMob", "DigitMob", "DmobileS", "EzzeMobi", "Farmobil", "Far-Sigh", "FuturaMo", "GmcGuard", "Guangdon", "HisenseM", "HostMobi", "IgiMobil", "IndigoMo", "InqMobil", "Ipmobile", "JdmMobil", "Jetmobil", "JustInMo", "KbtMobil", "L-3Commu", "LenovoMo", "LetvMobi", "LgElectr", "LiteonMo", "MemoboxS", "Microsof", "Mobacon", "Mobiis", "Mobilarm", "Mobileac", "MobileAc", "MobileAp", "Mobilear", "Mobileco", "MobileCo", "MobileCr", "MobileDe", "Mobileec", "MobileIn", "MobileMa", "MobileSa", "Mobileso", "MobileTe", "MobileXp", "Mobileye", "Mobilico", "Mobiline", "Mobilink", "Mobilism", "Mobillia", "Mobilmax", "Mobiltex", "Mobinnov", "Mobisolu", "Mobitec", "Mobitek", "MobiusTe", "Mobiwave", "Moblic", "Mobotix", "Mobytel", "Motorola", "NanjingS", "NecCasio", "P2Mobile", "Panasoni", "PandoraM", "Pointmob", "PoshMobi", "Radiomob", "RadioMob", "RapidMob", "RttMobil", "Shanghai", "Shenzhen", "SianoMob", "Smobile", "SonyEric", "SonyMobi", "Sysmocom", "T&AMobil", "TcmMobil", "TctMobil", "Tecmobil", "TinnoMob", "Ubi&Mobi", "Viewsoni", "Vitelcom", "VivoMobi", "XcuteMob", "XiamenMe", "YuduanMo", "Blackber"]

def main(args):
    f = open("/var/run/wifimap", 'w')
    f.write('%s'%os.getpid())
    f.close()
    app = Application(args)
  
    app.start()
    try:
        while True:
          time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        app.stop()
    print("stopped")
        


main(parse_args())
