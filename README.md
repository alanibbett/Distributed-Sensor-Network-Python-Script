# Distributed-Sensor-Network-Python-Script
Python files for the DSN
The Distributed Sensor Network was inspired by an article on the “Hackaday” Blog (Williams, 2016) that described a project that had many of the features required in the creation of a Distributed Sensor Network. The author of the project Mehdi Lauters (Lauters, 2016) published a project “Bordeaux: a digital urban exploration”. 

In the Bordeaux project, Lauters (2016) undertook a process of “war walking” (Tsui et al., 2010), where Lauters armed with a Raspberry Pi, configured with a GPS, Wi-Fi, and a Bluetooth sniffer explored the region around Bordeaux for six months and logged all the data found.

One of the aims of this research is to establish what participants find to be non-normal flows of information. Based on the work of (Lee & Kobsa, 2016) people find anonymous monitoring more disturbing than monitoring that could reasonably be expected to be occurring. This inspired the creation of inexpensive sensors based on freely available software. By creating sensing nodes that are inexpensive, easy to build and easy to use, the possibility of anonymous monitoring becomes more real to the participants in the research. The fact that the DSN nodes were inexpensive and manufactured by an individual was a key component of the intervention lesson as it brought home to the participants how easily the students IoT devices can be monitored and the kinds of data that could be discovered even though the students considered their devices secure.

The sensor node described here (DSNode) is a very simple, inexpensive and scalable sensing unit that can be built for a few dollars. All hardware components can be easily purchased online, and all of the code used is essentially zero cost. The only “custom” component in the design is the printed circuit board (PCB). The PCB was designed and built for this project to make the construction of a large number of nodes easier. The PCB is an optional component and could be replaced with a breadboard or even simple point to point wiring. The PCB does make the design much easier to work with.

Included in the design is an optional UPS card that allows the node to be powered from battery for a period of time.

The nodes described here, while designed to be “stand alone” can be interconnected by Wi-Fi, Ethernet or LoRa (Long Range) to form a distributed sensor network (DSN) that can provide data remotely to give a view of the parameters measured, in space as well as in time. The DSNode comprises a number of sub systems each of which can be modified to suit a particular application. The subsystems are CPU, Sensors/Communications, Power Supply, Case/Mounting.
THank you Medhi for your inspiration.
