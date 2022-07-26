# *****************************************************************************
# * | File        :	  epd7in5b_V2.py
# * | Author      :   Waveshare team
# * | Function    :   Electronic paper driver
# * | Info        :
# *----------------
# * | This version:   V4.2
# * | Date        :   2022-01-08
# # | Info        :   python demo
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


import os
import time
from src.CustomFormatter import CustomFormatter


if os.name == 'posix':
    import spidev
    import RPi.GPIO





# Display resolution
EPD_WIDTH       = 800
EPD_HEIGHT      = 480


class RaspberryPi:
    # Pin definition
    RST_PIN         = 17
    DC_PIN          = 25
    CS_PIN          = 8
    BUSY_PIN        = 24

    def __init__(self):
        self.GPIO = RPi.GPIO
        self.SPI = spidev.SpiDev()
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

    def digital_write(self, pin, value):
        self.GPIO.output(pin, value)

    def digital_read(self, pin):
        return self.GPIO.input(pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        self.SPI.writebytes(data)

    def spi_writebyte2(self, data):
        self.SPI.writebytes2(data)

    def module_init(self):
        # This is done by the configurator now!
        # self.GPIO.setmode(self.GPIO.BCM)
        # self.GPIO.setwarnings(False)
        self.GPIO.setup(self.RST_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.DC_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.CS_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.BUSY_PIN, self.GPIO.IN)

        # SPI device, bus = 0, device = 0
        self.SPI.open(0, 0)
        self.SPI.max_speed_hz = 4000000
        self.SPI.mode = 0b00
        return 0

    def module_exit(self):
        self.logger.debug("spi end")
        self.SPI.close()

        self.logger.debug("close 5V, Module enters 0 power consumption ...")
        self.GPIO.output(self.RST_PIN, 0)
        self.GPIO.output(self.DC_PIN, 0)

        self.GPIO.cleanup([self.RST_PIN, self.DC_PIN, self.CS_PIN, self.BUSY_PIN])




class EPD:
    def __init__(self):
        self.epdconfig = RaspberryPi()
        self.reset_pin = self.epdconfig.RST_PIN
        self.dc_pin = self.epdconfig.DC_PIN
        self.busy_pin = self.epdconfig.BUSY_PIN
        self.cs_pin = self.epdconfig.CS_PIN
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)

    # Hardware reset
    def reset(self):
        self.epdconfig.digital_write(self.reset_pin, 1)
        self.epdconfig.delay_ms(200) 
        self.epdconfig.digital_write(self.reset_pin, 0)
        self.epdconfig.delay_ms(4)
        self.epdconfig.digital_write(self.reset_pin, 1)
        self.epdconfig.delay_ms(200)   

    def send_command(self, command):
        self.epdconfig.digital_write(self.dc_pin, 0)
        self.epdconfig.digital_write(self.cs_pin, 0)
        self.epdconfig.spi_writebyte([command])
        self.epdconfig.digital_write(self.cs_pin, 1)

    def send_data(self, data):
        self.epdconfig.digital_write(self.dc_pin, 1)
        self.epdconfig.digital_write(self.cs_pin, 0)
        self.epdconfig.spi_writebyte([data])
        self.epdconfig.digital_write(self.cs_pin, 1)
    
    def send_data2(self, data): #faster
        self.epdconfig.digital_write(self.dc_pin, 1)
        self.epdconfig.digital_write(self.cs_pin, 0)
        self.epdconfig.SPI.writebytes2(data)
        self.epdconfig.digital_write(self.cs_pin, 1)

    def ReadBusy(self):
        self.logger.debug("e-Paper busy")
        self.send_command(0x71)
        busy = self.epdconfig.digital_read(self.busy_pin)
        while(busy == 0):
            self.send_command(0x71)
            busy = self.epdconfig.digital_read(self.busy_pin)
        self.epdconfig.delay_ms(200)
        self.logger.debug("e-Paper busy release")
        
    def init(self):
        if (self.epdconfig.module_init() != 0):
            return -1
            
        self.reset()
        
        # self.send_command(0x06)     # btst
        # self.send_data(0x17)
        # self.send_data(0x17)
        # self.send_data(0x38)        # If an exception is displayed, try using 0x38
        # self.send_data(0x17)

        self.send_command(0x01);			#POWER SETTING
        self.send_data(0x07);
        self.send_data(0x07);    #VGH=20V,VGL=-20V
        self.send_data(0x3f);		#VDH=15V
        self.send_data(0x3f);		#VDL=-15V

        self.send_command(0x04); #POWER ON
        self.epdconfig.delay_ms(100);
        self.ReadBusy();

        self.send_command(0X00);			#PANNEL SETTING
        self.send_data(0x0F);   #KW-3f   KWR-2F	BWROTP 0f	BWOTP 1f

        self.send_command(0x61);        	#tres
        self.send_data(0x03);		#source 800
        self.send_data(0x20);
        self.send_data(0x01);		#gate 480
        self.send_data(0xE0);

        self.send_command(0X15);
        self.send_data(0x00);

        self.send_command(0X50);			#VCOM AND DATA INTERVAL SETTING
        self.send_data(0x11);
        self.send_data(0x07);

        self.send_command(0X60);			#TCON SETTING
        self.send_data(0x22);

        self.send_command(0x65);
        self.send_data(0x00);
        self.send_data(0x00);
        self.send_data(0x00);
        self.send_data(0x00);
    
        return 0

    def getbuffer(self, image):
        img = image
        imwidth, imheight = img.size
        if(imwidth == self.width and imheight == self.height):
            img = img.convert('1')
        elif(imwidth == self.height and imheight == self.width):
            # image has correct dimensions, but needs to be rotated
            img = img.rotate(90, expand=True).convert('1')
        else:
            self.logger.warning("Wrong image dimensions: must be " + str(self.width) + "x" + str(self.height))
            # return a blank buffer
            return [0x00] * (int(self.width/8) * self.height)

        buf = bytearray(img.tobytes('raw'))
        # The bytes need to be inverted, because in the PIL world 0=black and 1=white, but
        # in the e-paper world 0=white and 1=black.
        for i in range(len(buf)):
            buf[i] ^= 0xFF
        return buf

    def display(self, imageblack, imagered):
        self.send_command(0x10)
        # The black bytes need to be inverted back from what getbuffer did
        for i in range(len(imageblack)):
            imageblack[i] ^= 0xFF
        self.send_data2(imageblack)

        self.send_command(0x13)
        self.send_data2(imagered)
        
        self.send_command(0x12)
        self.epdconfig.delay_ms(100)
        self.ReadBusy()
        
    def Clear(self):
        buf = [0x00] * (int(self.width/8) * self.height)
        buf2 = [0xff] * (int(self.width/8) * self.height)
        self.send_command(0x10)
        self.send_data2(buf2)
            
        self.send_command(0x13)
        self.send_data2(buf)
                
        self.send_command(0x12)
        self.epdconfig.delay_ms(100)
        self.ReadBusy()

    def sleep(self):
        self.send_command(0x02) # POWER_OFF
        self.ReadBusy()
        
        self.send_command(0x07) # DEEP_SLEEP
        self.send_data(0XA5)
        
        self.epdconfig.delay_ms(2000)
        self.epdconfig.module_exit()
