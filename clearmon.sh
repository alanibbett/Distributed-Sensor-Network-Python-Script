#!/bin/bash
echo 'Shutting down  monitoring'
sudo ifconfig mon0 down
echo 'Deleting virtual Interface'
sudo iw dev mon0 del 
echo 'done'
echo 'full list of  interfaces:'
sudo ifconfig -s

