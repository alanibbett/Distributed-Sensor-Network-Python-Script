#!/bin/bash
echo 'Setting up monitoring'
sudo iw phy phy0 interface add mon0 type monitor
sudo ifconfig mon0 up 
echo 'done'
echo 'full list of  interfaces:'
sudo ifconfig -s

