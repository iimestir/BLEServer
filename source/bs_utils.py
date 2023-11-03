# Utils module

import os
import logging
import sqlite3
import time
import configparser
import sys

# Process object handling the automail cycle
auto_mail_process = None
# Sensors informations are stored here,
# sensor_macs is a 1d array
# sensor_labels and sensor_uuids are both 2d arrays
sensor_macs = []
sensor_labels = []
sensor_uuids = []
# Used to convert the date format from a string to a SQL-compatible date
date_time = "DATETIME(substr(date,7,4) || '-' || substr(date,4,2) || '-' ||" \
    "substr(date,1,2) || ' ' || substr(date,12,2) || ':' || substr(date,15,2) || ':' ||" \
    "substr(date,18,2))"
# Active/Inactive sensors, will be send to the client
active_sensors = 0
inactive_sensors = 0
# Used to check if the DB is currently busy
db_process = False
# Service UUID stored in all sensors
sensor_service_uuid = None
# Frequency of sensor measurement acquisition
sensor_freq = None
# Server UUID
server_uuid = None
# Email address used to send mails
sender_mail = None
# Password of this email
sender_pass = None
# Number of days of data when user requests a manual mail
manual_mail_days = None
# InfluxDB hostname
influx_host = None
# InfluxDB credentials
influx_username = None
influx_password = None
influx_db = None

# Used the retrieve the config variables informations
def retrieveConfigParser():
    global sensor_service_uuid
    global sensor_freq
    global server_uuid
    global sender_mail
    global sender_pass
    global manual_mail_days
    global influx_host
    global influx_username
    global influx_password
    global influx_db
    
    config = configparser.ConfigParser()
    try:
        config.read("config.cfg")
        sensor_service_uuid = config["CONFIGURATION"]["sensor_service_uuid"]
        sensor_freq = int(config["CONFIGURATION"]["sensor_freq"])
        server_uuid = config["CONFIGURATION"]["server_uuid"]
        sender_mail = config["CONFIGURATION"]["sender_mail"]
        sender_pass = config["CONFIGURATION"]["sender_pass"]
        manual_mail_days = int(config["CONFIGURATION"]["manual_mail_days"])
        influx_host = config["CONFIGURATION"]["influx_host"]
        influx_username = config["CONFIGURATION"]["influx_username"]
        influx_password = config["CONFIGURATION"]["influx_password"]
        influx_db = config["CONFIGURATION"]["influx_db"]
    except Exception as e:
        logging.critical("ERROR OCCURED WHILE READING CONFIG.CFG FILE, CLOSING THE SERVER : %s", e)
        sys.exit(1)

# Checks if the values is a float object type
def isFloat(f):
    if(f == None):
        return False
    try:
        float(f)
        return True
    except ValueError:
        return False

# Returns device's bluetooth name
def getBTName():
    try:
        f = open("/etc/machine-info","r")
        lines = f.readlines()
        f.close()
        for l in lines:
            if(l.startswith("PRETTY_HOSTNAME=")):
                return l.split("=")[1].replace(';','').rstrip()
        return "Untitled"
    except Exception as e:
        logging.error("Error occured while getting device BT name")
        return "Untitled"

# Get the first or last date from the database
# days : number of days to read in the DB
# if days > 0 : get the first day of the data acquisition
# if days = 0 : get the last day
def getDate(days):
    ret = ""
    try:
        conn = sqlite3.connect("sensors.db")
        c = conn.cursor()
        if(days > 0):
            query = "SELECT * FROM("
            query += "SELECT * FROM sensors"
            query += " WHERE " + date_time + " BETWEEN DATETIME('now','localtime','-"+str(days)+" days') AND DATETIME('now','localtime')"
            query += " ORDER BY " + date_time
            query += ")"
            query += " ORDER BY " + date_time + " ASC LIMIT 1"
            sel = c.execute(query)
        else:
            query = "SELECT * FROM("
            query += "SELECT * FROM sensors"
            query += " ORDER BY " + date_time
            query += ")"
            query += " ORDER BY " + date_time + " DESC LIMIT 1"
            sel = c.execute(query)
        for i, row in enumerate(sel):
            for j, value in enumerate(row):
                ret = row[j].split(" ")[0]
                break
    except Exception as e:
        logging.error(e)
        ret = None
    finally:
        if conn:
            conn.close()
        return ret  

# Registers how many sensors are working and how many aren't
# values : Sensors data
def registerStatus(values):
    global active_sensors
    global inactive_sensors

    active_sensors = 0
    inactive_sensors = 0
    for sensor_values in values:
        if(all(x is None for x in sensor_values)):
            inactive_sensors += 1
        else:
            active_sensors += 1
    logging.info("Sensors status registered")        
    logging.info("Sensors status -> Active : %s ; Inactive : %s ",active_sensors, inactive_sensors)

# DBs and log files cleaning, used for memory management     
def cleanUp():
    global db_process

    while(db_process):
        time.sleep(0.100)

    listFiles = os.listdir(os.getcwd())
    for f in listFiles:
        if(f.startswith('sensors') and f != "sensors.db" and f != "sensors_"+getBTName()+".xlsx"):
            try:
                os.remove(f)
            except Exception as e:
                logging.error("Failed to delete the file %s",f)

    try:
        if(os.path.exists("sensors.db")):
            if(os.stat("sensors.db").st_size > 100000000):
                os.remove("sensors.db")
        if(os.path.exists("log")):
            if(os.stat("log").st_size > 100000000):
                f = open('log', 'r+')
                f.truncate(0)
                f.close()
        if(os.path.exists("backup.db")):
            if(os.stat("backup.db").st_size > 100000000):
                os.remove("backup.db")
    except Exception as e:
        logging.error("Error occured while cleaning up : %s", e)
