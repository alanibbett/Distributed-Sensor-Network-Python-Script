########
#globals
# debug messages
DEBUGFLAG = 0
# Raspberry Pi pin configuration:
#RST = 24
RST = None
# Note the following are only used with SPI:
#DC = 23
DC= None
#SPI_PORT = 0
SPI_PORT = None
#SPI_DEVICE = 0
SPI_DEVICE = None

#screen configuration
# height of each text line in pixels
TEXT_LINE_X = 10
TEXT_Y_OFFSET = 5
# this oled has two sections, 16 pixel yellow bar at the top and then the remaining 48 pixels are blue
# this var marks the start of the main section of the screen and anything to be displayed in it should be offset by it
MAIN_X = 16
MAX_ITEM_PERSCREEN = 4
SECOND_SCREEN = False
# font settings
# font name and location
FONT_NAME = "./src/oledmenus/menusystem/fonts/DejaVuSerif.ttf"
# font size
FONT_SIZE = 10

# screen saver setting
SCREEN_SAVER_TYPE = 0	# 0 = image, 1 = shapes drawing
SCREEN_SAVER_TIMEOUT = 10
SCREEN_SAVER_PIC = "./src/oledmenus/happycat_oled_64.ppm"
SCREEN_SAVER_PIC = "./src/oledmenus/oledIcon.ppm"

# Time to wait between button presses
BUTTON_SLEEP_TIME = 0.25

# Location of menu files
# MENU_FOLDER = "./menus"
#MENU_FOLDER = "./example-menus/"
MENU_FOLDER = "./src/oledmenus/dsnmenus/"
# var to track selected menu 
selectedMenu = 0

#display object
display = None

#these values come from the thread.run method in the scanmap app
GPS_MODE = 0
GPS_ACCURACY = 0
GPS_ESTX = 0
GPS_ESTY = 0
RADIO = None
APPLICATION = None
############


