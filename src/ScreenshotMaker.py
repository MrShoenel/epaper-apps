import io
import os
from src.CustomFormatter import CustomFormatter
from time import sleep
from PIL import Image #, ImageOps, ImageEnhance
from selenium import webdriver
import signal


class ScreenshotMaker:

    def __init__(self, driver: str='gecko'):
        self.driver_name = driver

        if driver == 'gecko':
            options = webdriver.FirefoxOptions()
            options.add_argument('--headless')
            self.driver = webdriver.Firefox(options=options)
        elif driver == 'chrome':
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--hide-scrollbars')
            chrome_options.add_argument('--force-device-scale-factor=1')
            if os.name == 'nt':
                chrome_options.binary_location = 'C:\\Program Files (Portable)\\chromium\\chrome.exe'
            self.driver = webdriver.Chrome(options=chrome_options)
        else:
            raise Exception(f'Driver "{driver}" not known.')
        
        self.driver.set_page_load_timeout(120.0)
        self.logger = CustomFormatter.getLoggerFor(self.__class__.__name__)
    
    def __del__(self):
        pid = -1
        if self.driver_name == 'gecko':
            pid = int(self.driver.capabilities['moz:processID'])
        else:
            pass # not supported currently

        try:
            self.driver.close()
        except:
            self.logger.debug('driver.close() threw.')
            pass # don't care at all, we just want it gone!

        # Have separate try-block in case close() throws:
        try:
            self.driver.quit()
        except:
            self.logger.debug('driver.quit() threw.')
            pass

        if pid > 0:
            self.logger.debug(f'Also attempting to kill process with ID=${pid}.')
            sig = signal.SIGTERM if os.name == 'nt' else signal.SIGKILL
            try:
                os.kill(pid, sig)
            except:
                pass



    def setViewportSize(self, width, height):
        # Extract the current window size from the driver
        current_window_size = self.driver.get_window_size()

        # Extract the client window size from the html tag
        html = self.driver.find_element_by_tag_name('html')
        inner_width = int(html.get_attribute("clientWidth"))
        inner_height = int(html.get_attribute("clientHeight"))

        # "Internal width you want to set+Set "outer frame width" to window size
        target_width = width + (current_window_size["width"] - inner_width)
        target_height = height + (current_window_size["height"] - inner_height)

        self.driver.set_window_rect(width=target_width, height=target_height)

        return self
    
    def screenshot(self, width: int, height: int, url: str, **kwargs) -> list[Image.Image, Image.Image]:
        self.setViewportSize(width=width, height=height)
        self.driver.get(url=url)
        sleep(5)
        
        img_bytes = self.driver.get_screenshot_as_png()
        img = Image.open(io.BytesIO(initial_bytes=img_bytes))
        img = img.crop((0, 0, width, height))

        # I recommend in text-heavy screenshots to enhance contrast with ~1.7.
        # Before writing the image to the display, convert to grayscale also
        # helps to smooth out some crispiness.

        #img = ImageOps.autocontrast(img)
        #img = ImageEnhance.Contrast(img).enhance(1.7)
        # Grayscale does a bit but it is not a big effect.
        #img = ImageOps.grayscale(img)

        # Also, let's return a red and a black image:
        redimg = img.copy()
        rpixels = redimg.load()
        blackimg = img
        bpixels = blackimg.load()

        for i in range(redimg.size[0]):
            for j in range(redimg.size[1]):
                if rpixels[i, j][0] <= rpixels[i, j][1] and rpixels[i, j][0] <= rpixels[i, j][2]:
                    rpixels[i, j] = (255, 255, 255)
                elif bpixels[i, j][0] > bpixels[i, j][1] and bpixels[i, j][0] > bpixels[i, j][2]:
                    bpixels[i, j] = (255, 255, 255)

        return blackimg, redimg
