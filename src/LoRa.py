
import threading
import time
import sys
import subprocess
import busio
from digitalio import DigitalInOut, Direction, Pull
import board
from adafruit_tinylora.adafruit_tinylora import TTN, TinyLoRa
import random
from . import ttn


class lora_radio ():
    def __init__(self,cs=board.CE1,irq=board.D22,rst=board.D25, country='AU'):
        # TinyLoRa Board Configuration
        self.spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        self.cs = DigitalInOut(cs)
        self.irq = DigitalInOut(irq)
        self.rst = DigitalInOut(rst)
        self.data_pkt = []
        self.country = country
        # set up TTN Information
        # TTN Device Address, 4 Bytes, MSB
        self.devaddr = ttn.devaddr
        
        # TTN Network Key, 16 Bytes, MSB
        self.nwkey = ttn.nwkey

        # TTN Application Key, 16 Bytess, MSB
        self.app = ttn.app
        
        # Initialize ThingsNetwork configuration
        self.ttn_config = TTN(self.devaddr, self.nwkey, self.app, self.country)
        # Initialize lora object
        self.lora = TinyLoRa(self.spi, self.cs, self.irq, self.rst, self.ttn_config)

        # time to delay periodic packet sends (in seconds)
        self.data_pkt_delay = 300.0


    def send_pi_data_periodic(self,data = []):
        threading.Timer(self.data_pkt_delay, self.send_pi_data_periodic).start()
        if data:
            self.send_pi_data(data)
        else:
            self.send_pi_data(self.dummy_packet())
            #print ("Dummy")
            
        print("Sending periodic data...")
        

    def send_pi_data(self,data = []):
        self.data_pkt = data
        # Send data packet
        self.lora.send_data(self.data_pkt, len(self.data_pkt), self.lora.frame_counter)
        self.lora.frame_counter += 1
        #print('LoRa Data sent!')
        time.sleep(0.2)

    def dummy_packet(self):
        #creates a dummy packet for testing purposes
        data_pkt = []
        data_pkt.clear()  # out with the old
        #in with the new
        # Encode float as int
        cpu = int(self.get_CPU() * 100)
        df = int(self.get_df()*100)
        #build the LPP frame
        self.add_di_payload(data_pkt,1,random.randint(0,1)) #App start
        self.add_di_payload(data_pkt,2,random.randint(0,1)) #App initiated reboot
        self.add_di_payload(data_pkt,3,random.randint(0,1)) # app initated shutdown
        self.add_di_payload(data_pkt,4,random.randint(0,1)) #GPS Lock
        self.add_di_payload(data_pkt,5,random.randint(0,1)) # GPS Poller
        self.add_di_payload(data_pkt,6,random.randint(0,1)) #Bluetooth Poller
        self.add_di_payload(data_pkt,7,random.randint(0,1)) #Wifi Poller
        self.add_di_payload(data_pkt,8,random.randint(0,1)) #disp poller
        
        self.add_ai_payload(data_pkt,40,df)      
        self.add_ai_payload(data_pkt,41,cpu)

        
        
        return data_pkt
        
        
    def get_hostname(self):
        cmd = "hostname"
        return subprocess.check_output(cmd, shell = True ) 
    
    def get_CPU(self):
        # read the raspberry pi cpu load
        cmd = "top -bn1 | grep load | awk '{printf \"%.1f\", $(NF-2)}'"
        CPU = subprocess.check_output(cmd, shell = True )
        return float(CPU)

    def get_df(self):
        # read the raspberry disk space
        cmd = "df -h | tr -s ' ' | grep root | cut -d ' ' -f 5 | tr '%' ' '"
        df = subprocess.check_output(cmd, shell = True )
        return float(df)
    
    def add_ai_payload(self,payload,channel=1,value=0):
        payload.append(channel & 0xFF)
        payload.append(0x02) #datatype for analogue data
        payload.append((value>>8) & 0xFF)
        payload.append(value & 0xFF)
    
    def add_di_payload(self,payload,channel=64,value=0):
        payload.append(channel & 0xFF)
        payload.append(0x00) #datatype for digital input
        payload.append(value & 0xFF)
    
    def update_status(self,channel=0,data=1,mode=0):
        '''
        This function send a status update on the channel passed
        to it. The data passed to it should be a binary and the mode
        determines if the function sends the update as a pulse.
        mode 0 : send the data and return
        mode 1 : send a '1' wait 1 second send a '0' - ignores the data and returns
        otherwise just returns
        '''
        pkt = []
        pkt.clear()
        if mode == 0:
            self.add_di_payload(pkt,channel,data)
            self.send_pi_data(pkt)
            pkt.clear()
            return
        elif mode == 1:
            self.add_di_payload(pkt,channel,1)
            self.send_pi_data(pkt)
            pkt.clear()
            time.sleep(1)
            self.add_di_payload(pkt,channel,0)
            self.send_pi_data(pkt)
            pkt.clear()
            return
            
        
    
    
    
    
    
def main():
    
    radio = lora_radio()
    while True:
        command = input("Command (q to quit) > ")
        #print ("command was %s"%(command))
        if command == 'q':
            break
        if command == 'p':
            radio.send_pi_data_periodic()
        if command == 'fast':
            radio.data_pkt_delay = 5.0
            print ("Speed %s"%(radio.data_pkt_delay))
        
        if command == 'slow':
            radio.data_pkt_delay = 300.0
            print ("Speed %s"%(radio.data_pkt_delay))
        
        radio.send_pi_data(radio.dummy_packet())
        time.sleep(.1)

if __name__ == "__main__":
    main()
    sys.exit()

    