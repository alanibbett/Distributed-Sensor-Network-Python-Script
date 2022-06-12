''' 
This file contains all of the set up information for the TTN




'''


# TTN Device Address, 4 Bytes, MSB
devaddr = bytearray([0x26, 0x01, 0x17, 0xBA ] )

# TTN Network Key, 16 Bytes, MSB
nwkey = bytearray([ \
0x21, 0xA4, 0xE9, 0xB3, \
0xC6, 0xB3, 0x10, 0xAC, \
0xC3, 0x68, 0x58, 0xE0, \
0x42, 0x3D, 0xE2, 0x3C ] )

# TTN Application Key, 16 Bytess, MSB
app = bytearray( [ 0x3C, 0xA2, 0x29, 0x84,\
0xF7, 0x3A, 0x01, 0x9D,\
0x75, 0x83, 0x9F, 0x7E,\
0x13, 0x60, 0xC1, 0x99 ] )