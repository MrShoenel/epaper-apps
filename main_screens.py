import os
import sys
import signal
from os.path import join, abspath
from PIL import Image
from src.Configurator import Configurator
from src.ScreenshotMaker import ScreenshotMaker


if len(sys.argv) < 2:
    raise Exception('Expecting exactly one argument: the name of the screen.')


conf_name = sys.argv[1]
conf = Configurator.fromJson(path='config.json')
screen_conf = conf.getScreenConfig(conf_name)
data_folder = conf.getGeneralConfig()['data_folder'][os.name]


if __name__ == "__main__":
    if os.name != 'nt':
        os.setpgrp()

    try:
        sm = ScreenshotMaker(driver=conf.getGeneralConfig()['screen_driver'])
        blackimg, redimg = sm.screenshot(**screen_conf)
        with open(file=abspath(join(data_folder, f'{conf_name}_b.png')), mode='wb') as fp:
            blackimg.save(fp)
        with open(file=abspath(join(data_folder, f'{conf_name}_r.png')), mode='wb') as fp:
            redimg.save(fp)
        
        del sm
    except Exception as e:
        print(e)
    finally:
        if os.name == 'nt':
            os.kill(os.getpid(), signal.SIGINT)
        else:
            os.killpg(os.getpgid(os.getpid()), signal.SIGINT)
