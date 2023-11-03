# BlueServer by IMESTIR Ibrahim - 43792@etu.he2b.be

import os
import logging
import sys
import datetime
import threading
import multiprocessing
import bs_utils
from datetime import datetime
from bs_socket import server
from bs_sensor import retrieveSensorsInformations, sensor
from bs_mail import startAutoMailProcess
from bs_utils import retrieveConfigParser
from bs_databases import handleOldDB

#----------------- MAIN -----------------#
if __name__ == '__main__':
    if(os.path.exists('log')):
        os.remove('log')
    logging.basicConfig(filename='log',level=logging.DEBUG,format='%(asctime)s %(levelname)s:%(message)s', datefmt='[%d/%m/%Y %H:%M:%S]')
    
    if(sys.platform != "linux"):
        logging.critical("UNSUPPORTED OS, THIS SERVER WORKS ONLY WITH A LINUX ENVIRONNEMENT, CLOSING THE SERVER")
        sys.exit(1)
        
    retrieveConfigParser()
        
    if(bs_utils.sensor_freq < 0 or bs_utils.manual_mail_days < 0 or bs_utils.manual_mail_days > 366):
        logging.critical("INVALID FREQUENCY VALUE, CLOSING THE SERVER")
        sys.exit(1)

    if(os.path.exists('backup.db')):
        os.system("sudo mv backup.db backup_" + datetime.today().strftime("%Y-%m-%dT%H:%M:%SZ") + ".db")

    os.system("sudo hciconfig hci0 down")
    os.system("sudo hciconfig hci0 up")

    retrieveSensorsInformations()
    handleOldDB()

    threading.Thread(target=server).start()
    threading.Thread(target=sensor).start()
    threading.Thread(target=startAutoMailProcess).start()