
#!/bin/bash
cd /home/pi/wifiScanMap
echo 'Starting'
cd /home/pi/wifiScanMap
echo ".... now starting scanner"
sudo ./scanmap.py  -m -a 60 -p " -34.08134944,150.78171934" 
#sudo ./scanmap.py  -m -a 65 

