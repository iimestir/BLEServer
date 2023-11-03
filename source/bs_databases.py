# Databases module 

import pytz
import datetime
import sqlite3
import os
import time
import logging
import bs_utils
from bs_utils import getBTName, isFloat
from tzlocal import get_localzone
from influxdb import InfluxDBClient
from datetime import datetime

# Formats (for influxdb) and changes the timezone of a date string
# strdate : date (string format)
def dateToUTC(strdate):
    timezone = pytz.timezone(str(get_localzone()))
    date = timezone.localize(datetime.strptime(strdate, '%d/%m/%Y %H:%M:%S'))
    dateUTC = date.astimezone(pytz.utc)
    return dateUTC.strftime("%Y-%m-%dT%H:%M:%SZ")

# Writes the sensors data do the LoRaWAN file (used to send data to the LoRaWAN server)
# json_body : JSON formatted object, sensors data 
def writeToLoRaFile(json_body):
    logging.info("Writing values to the LoRaWAN file")
    with open("lora", "a+") as file:
        for i in range(len(json_body)):
            file.write(str(json_body[i]).replace("'", '"').replace('"central": "' + getBTName() + '", ', '') + "\n")

# Used to send the backup data to Grafana
# backup_db : Backup database path
def completeInfluxDB(backup_db):
    json_body = []
    err = False
    try:
        conn = sqlite3.connect(backup_db)
        c = conn.cursor()
        c.execute("SELECT * FROM sensors")
        records = c.fetchall()
        measurement = [description[0] for description in c.description]
        for i in range(len(records)):
            date = records[i][0]
            for j in range(1, len(records[i])):
                if(isFloat(records[i][j])):
                    json_body.append({
                        "measurement": measurement[j].split("_")[0],
                        "time": dateToUTC(date),
                        "tags": {"central" : getBTName(),"device": int(measurement[j].split("_")[1])},
                        "fields": {"value": float(records[i][j])}
                    })
    except Exception as e:
        logging.error(e)
        err = True
    finally:
        if conn:
            conn.close()
        if(err):
            return

    try:
        client = InfluxDBClient(host=bs_utils.influx_host, port=8086, username=bs_utils.influx_username, password=bs_utils.influx_password, retries=1)
        client.switch_database(bs_utils.influx_db)
        client.write_points(json_body)
        os.remove(backup_db)
    except Exception as e:
        logging.error("Error occured while sending BACKUP DB to influxDB : %s", e)

# Send sensor data to an influxDB (Grafana)
# values : values to send
# date : time when the values were acquired
def sendToInfluxDB(values, date):
    json_body = []
    for i in range(len(values)):
        for j in range(len(values[i])):
            if(isFloat(values[i][j])):
                json_body.append({
                    "measurement": bs_utils.sensor_labels[i][j],
                    "time": dateToUTC(date),
                    "tags": {"central" : getBTName(),"device": i+1},
                    "fields": {"value": float(values[i][j])}
                })
                
    try:
        client = InfluxDBClient(host=bs_utils.influx_host, port=8086, username=bs_utils.influx_username, password=bs_utils.influx_password, retries=1)
        client.switch_database(bs_utils.influx_db)
        client.write_points(json_body)
        handleBackupDB()
    except Exception as e:
        logging.error("Error occured while sending data to influxDB : %s", e)
        logging.info("Storing values in backup DB grafana")
        store("backup.db", values, date)
        writeToLoRaFile(json_body)

# Used to store the sensors data in the DB
# db : DB path
# values : values to store
# date : time when values were acquired
def store(db, values, date):
    conn = None
    if(date == "" or date == None):
        date = datetime.today().strftime('%d/%m/%Y %H:%M:%S')

    try:
        while(bs_utils.db_process):
            time.sleep(0.100)
        db_process = True
        
        conn = sqlite3.connect(db)
        c = conn.cursor()
        sql = "CREATE TABLE IF NOT EXISTS sensors(date text NOT NULL"
        sql2 = "INSERT INTO sensors(date"
        for i in range(len(values)):
            for j in range(len(values[i])):
                sql += ", " + str(bs_utils.sensor_labels[i][j] + "_" + str(i+1)) + " real"
                sql2 += ", " + str(bs_utils.sensor_labels[i][j] + "_" + str(i+1))
        
        sql += ");"
        sql2 += ") VALUES(?"
        sqlval = (date,)
        for i in range(len(values)):
            for j in range(len(values[i])):
                sql2 += ",?"
                if(values[i][j] == None):
                    sqlval += ("",)
                else:
                    sqlval += (values[i][j],)
        sql2 += ");"
        
        c.execute(sql)
        c.execute(sql2, sqlval)
        conn.commit()
    except Exception as e:
        logging.error("Error occured while storing values in the DB : %s", e)
    finally:
        if conn:
            conn.close()
        db_process = False

# Used to upload the backup data on Grafana
def handleBackupDB():
    listFiles = os.listdir(os.getcwd())
    for f in listFiles:
        if(f.startswith('backup_') or f.startswith('backup.db')):
            logging.info("Backup DB %s found, Sending it to grafana", f)
            completeInfluxDB(f)

# Used to transform a 2d array into a 1d array
def flatten2DArray(array):
    result = []
    for i in range(len(array)):
        for j in range(len(array[i])):
            result.append(array[i][j])

    return result

# Checks if the nodes config file is compatible with the current DB
# if not, delete this DB
def handleOldDB():
    if not (os.path.exists('sensors.db')):
        return

    temp = flatten2DArray(bs_utils.sensor_labels)
    try:
        conn = sqlite3.connect('sensors.db')
        c = conn.cursor()
        c.execute("SELECT * FROM sensors")
        records = c.fetchall()

        measurement = [description[0] for description in c.description]
        measurement = [item.split("_")[0] for item in measurement]
        measurement.pop(0)
        if(temp != measurement):
            logging.warning("Sensors configuration differs from the old DB, deleting...")
            os.remove('sensors.db')
    except Exception as e:
        os.remove('sensors.db')
    finally:
        if conn:
            conn.close()