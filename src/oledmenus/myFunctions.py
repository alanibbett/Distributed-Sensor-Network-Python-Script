#imports 
import sys
sys.path.insert(0, "../")
sys.path.insert(0, "./")
import globalsettings
import time
import ifcfg


# functions which are called by function handlers are placed in the MenuFunc_Base class
class MenuFunc_Base:
	def myFunction1():
		display = globalsettings.display
		print("This will print out the status of the daemons")
		display.clearMainScreen()
		display.clearTitle()
		display.drawTextLine("daemons are:",0)
		display.drawTextLine("running",1)
		time.sleep(4)
		display.clearMainScreen()
		
		if (globalsettings.DEBUGFLAG >= 1):
			print("This will print out the status of the daemons")

	def myFunction2():
		gps_lock_mode = str(globalsettings.GPS_MODE)
		gps_accuracy = str(globalsettings.GPS_ACCURACY)
		gps_estx = str(globalsettings.GPS_ESTX)
		gps_esty = str(globalsettings.GPS_ESTY)
		display = globalsettings.display
		display.clearMainScreen()
		display.clearTitle()
		display.drawTitle("GPS Lock Mode:")
		display.drawTextLine(gps_lock_mode,0)
		display.drawTextLine("Precision Req "+gps_accuracy,1)
		display.drawTextLine("est x "+ gps_estx+" est y "+ gps_esty,2)
		if globalsettings.GPS_MODE <= 1:
			display.drawTextLine("No LOCK:",3)
		else:
			display.drawTextLine("GPS Lock GOOD:",3)
			
		time.sleep(5)
		display.clearMainScreen()
		
		
		
		if (globalsettings.DEBUGFLAG >= 1):
			print("This is will print out the status of GPS")
	
	def shutdown():
		radio = globalsettings.RADIO
		radio.update_status(3,1,1) #send to channel 3 (app shutdown a 1 in mode 0)
		globalsettings.APPLICATION.clear_LoRa_console()
		
		command = "/usr/bin/sudo /sbin/shutdown -h now"
		import subprocess
		print("shutting down")
		p = subprocess.run(command.split())
		
	def restart():
		radio = globalsettings.RADIO
		radio.update_status(2,1,1) #send to channel 2 (app reboot a 1 in mode 0)
		globalsettings.APPLICATION.clear_LoRa_console()
		
		command = "/usr/bin/sudo /sbin/shutdown -r now"
		import subprocess
		print("restarting now")
		p = subprocess.run(command.split())
		
	def ifcfg():
		count = 0
		display = globalsettings.display
		display.clearMainScreen()
		display.drawTitle("Found interfaces...")
		for name in ifcfg.interfaces():
			display.drawTextLine(name,count)
			count = count+1
		time.sleep(5)
		display.clearMainScreen()			
		
	def ipaddresses():
		count = 0
		display = globalsettings.display
		display.clearMainScreen()
		display.drawTitle("IP addresses...")
		for name, intf in ifcfg.interfaces().items():
			display.drawTextLine(name + "-> " + str(intf['inet']) ,count)
			count = count+1
		time.sleep(5)
		display.clearMainScreen()
		
# dictionary to hold function handlers
functionHandlersDictionary = { "myFunction1":  [MenuFunc_Base.myFunction1, "My function 1"], "myFunction2": [MenuFunc_Base.myFunction2, "My Function 2"], "shutdown": [MenuFunc_Base.shutdown, "shutdown"],"restart": [MenuFunc_Base.restart, "restart"],"ifcfg": [MenuFunc_Base.ifcfg, "ifcfg"],"ipaddresses":[MenuFunc_Base.ipaddresses,"ipaddresses"] }
