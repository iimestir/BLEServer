# Sensors module

import logging
import struct
import io
import sys
import datetime
import threading
import time
import bs_utils
import re
from numpy import empty
from bs_databases import sendToInfluxDB, store
from datetime import datetime, timedelta
from bluepy import btle

# Used to store sensor values (each sensor is in a different thread)
values = []

# Poll the data from a single sensor, will try to connect 3 times on every sensor if
# an error occured.
# mac : Sensor MAC address
# uuids : Sensor measurement UUIDS
# index : Sensor values index in the "values" array
def pollSensor(mac, uuids, index):
    global values

    logging.info("Connecting to sensor : %s", mac)
    retries = 0
    acquiredValues = False

    while(acquiredValues == False and retries < 3):
        sensor = None
        sensor_values = []

        try:
            if not(re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower())):
                acquiredValues = True
                raise Exception("Invalid mac address : " + mac)

            sensor = btle.Peripheral(mac, btle.ADDR_TYPE_PUBLIC)
            service = sensor.getServiceByUUID(btle.UUID(bs_utils.sensor_service_uuid))

            for uu in uuids:
                car = service.getCharacteristics(btle.UUID(uu))[0]
                value = round(struct.unpack('f', car.read())[0],4)
                if(value != 0):
                    sensor_values.append(value)
                else:
                    sensor_values.append(None)
        except Exception as e:
            logging.error("%s : %s", mac, e)
            while(len(sensor_values) < len(uuids)):
                sensor_values.append(None)
        finally:
            if(sensor != None):
                sensor.disconnect()

            if(all(elem == None for elem in sensor_values) and acquiredValues == False):
                retries += 1
                if(retries < 3):
                    logging.info("Retrying connection with : %s (%s)", mac, retries)
                    time.sleep(1.5)
                else:
                    logging.error("Failed to establish communication with : %s", mac)
            else:
                acquiredValues = True
            values[index] = sensor_values

# Poll data from the declared sensors
# date : time when the poll started
def datapoll(date):
    global values

    if(len(bs_utils.sensor_macs) <= 0):
        logging.warning("No sensor declared in nodes.cfg")
        return

    values = empty(len(bs_utils.sensor_macs), dtype=object)
    threads = []
    for i in range(len(bs_utils.sensor_macs)):
        mac = bs_utils.sensor_macs[i]
        uuids = bs_utils.sensor_uuids[i]
        threads.append(threading.Thread(target=pollSensor, args=(mac, uuids, i,)))
        threads[i].start()
        time.sleep(0.5)

    while(any(x.is_alive() for x in threads)):
        time.sleep(0.5)

    logging.info("Storing sensor values in the DB : %s", values)
    store("sensors.db", values, date)
    bs_utils.registerStatus(values)
    sendToInfluxDB(values, date)

# Get the sensors informations (macs, labels, uuids) from nodes.cfg
def retrieveSensorsInformations():
    logging.info("Reading nodes config file...")
    try:
        f = None
        f = io.open("nodes.cfg", "r", encoding="utf8")
        lines = f.readlines()
        if(len(lines) < 3):
            raise Exception("Invalid or empty sensors config file.")

        for line in lines:
            if(line.startswith("mac")):
                m = "".join(line.split())
                mac = m.split("mac=")[1]
                bs_utils.sensor_macs.append(mac)
            elif(line.startswith("labels")):
                l = "".join(line.split())
                labels = l.split("labels=")[1].split(",")
                labels = [re.sub('[^A-Za-z0-9]+', '', item) for item in labels]
                bs_utils.sensor_labels.append(labels)
            elif(line.startswith("uuids")):
                u = "".join(line.split())
                uuids = u.split("uuids=")[1].split(",")
                bs_utils.sensor_uuids.append(uuids)
    except Exception as e:
        logging.critical("ERROR OCCURED WHILE READING SENSORS FILE, CLOSING THE SERVER : %s", e)
        if(f != None):
            f.close()
        sys.exit(1)
    finally:
        if(f != None):
            f.close()
            
    if(len(bs_utils.sensor_labels) != len(bs_utils.sensor_uuids)):
        logging.critical("INVALID SENSOR CONFIG FILE, UUIDS AND LABELS SIZE DIFFERS, CLOSING THE SERVER")
        sys.exit(1)
    for i in range(len(bs_utils.sensor_labels)):
        if(len(bs_utils.sensor_labels[i]) != len(bs_utils.sensor_uuids[i])):
            logging.critical("INVALID SENSOR CONFIG FILE, UUIDS AND LABELS SIZE DIFFERS, CLOSING THE SERVER")
            sys.exit(1)

# Sensor queue function
def sensor():
    logging.info("Listening to sensors...")
    date = datetime.now()
    while True:
        threading.Thread(target=bs_utils.cleanUp).start()
        threading.Thread(target=datapoll, args=(date.strftime('%d/%m/%Y %H:%M:%S'),)).start()
        time.sleep(bs_utils.sensor_freq*60)
        date += timedelta(minutes=bs_utils.sensor_freq)
        
        err = (date-datetime.now()).total_seconds()
        if(abs(err) >= 45):
            date = datetime.now()