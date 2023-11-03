# Socket module

import logging
import sqlite3
import os
import time
import bs_utils
from bluetooth import *
from bluepy import btle
from bs_mail import enableAutoMailProcess, sendMail

# Sends all the sensors measurement to the client
# client_sock : client socket
def sendSensorsTypes(client_sock):
    logging.info("Sending sensors types to client...")
    types = []
    
    try:
        conn = sqlite3.connect("sensors.db")
        c = conn.cursor()
        query = "SELECT * FROM("
        query += "SELECT * FROM sensors"
        query += " WHERE " + bs_utils.date_time + " BETWEEN DATETIME('now','localtime','-6 hours') AND DATETIME('now','localtime')"
        query += " ORDER BY " + bs_utils.date_time
        query += ")"
        query += " ORDER BY " + bs_utils.date_time + " ASC"
        c.execute(query)
        records = c.fetchall()
        measurement = [description[0] for description in c.description]

        for i in range(len(records)):
            date = records[i][0]
            for j in range(1, len(records[i])):
                if(bs_utils.isFloat(records[i][j]) and measurement[j].split('_')[0] not in types):
                    types.append(measurement[j].split('_')[0])
                    
        req = "types#"
        for t in types:
            req += t + "!"

        client_sock.send(req + "\n")
    except Exception as e:
        logging.error("Error occured while sending sensors types to the client : %s", e)
    finally:
        if conn:
            conn.close()

# Used to connect the RPI to a Wi-Fi
# DOESN'T WORK PROPERLY
# SSID : Wi-Fi SSID
# pwd : Wi-Fi password    
def wifiConnect(SSID, pwd):
    # TODO : Doesn't work properly
    logging.info("Connecting to Wi-Fi...")
    if(SSID == "" or SSID == None):
        logging.error("No SSID specified.")
        return

    logging.info("SSID : %s", SSID)
    logging.warning("WARNING : THIS FUNCTIONNALITY DOESN'T WORK PROPERLY")
    f = open('/etc/wpa_supplicant/wpa_supplicant.conf', 'a')

    if(pwd == "" or pwd == None):
        f.write('\nnetwork={\n\tssid="' + SSID + '"\n}')
    else: 
        f.write('\nnetwork={\n\tssid="' + SSID + '"\n\tpsk="' + pwd + '"\n}')

    f.close()
    os.system("sudo wpa_cli -i wlan0 reconfigure")

# Sends the sensors values of a measurement to the client
# client_sock : client socket
# sensortype : measurement asked by the client
def sendSensorsValues(client_sock, sensortype):
    if(sensortype == "" or sensortype == None):
        logging.error("Invalid sensor type specified")
        return
    
    logging.info("Sending sensors values to client...")
    tuples = []
    try:
        conn = sqlite3.connect("sensors.db")
        c = conn.cursor()
        query = "SELECT * FROM("
        query += "SELECT * FROM sensors"
        query += " WHERE " + bs_utils.date_time + " BETWEEN DATETIME('now','localtime','-6 hours') AND DATETIME('now','localtime')"
        query += " ORDER BY " + bs_utils.date_time
        query += ")"
        query += " ORDER BY " + bs_utils.date_time + " ASC"
        c.execute(query)
        records = c.fetchall()
        measurement = [description[0] for description in c.description]

        for i in range(len(records)):
            date = records[i][0]
            for j in range(1, len(records[i])):
                if(bs_utils.isFloat(records[i][j]) and sensortype == measurement[j].split('_')[0]):
                    tuples.append((measurement[j].split('_')[0], measurement[j].split('_')[1], date, float(records[i][j]),))

        tuples.sort(key = lambda x : (x[0], x[1]))
        req = "values"
        tt = None
        for t in tuples:
            if(tt == (t[0],t[1],)):
                req += str(t[2]) + "_" + str(t[3]) + "!"
            else:
                tt = (t[0],t[1],)
                req += "#" + str(t[0]) + "_" + str(t[1]) + "!" + str(t[2]) + "_" + str(t[3]) + "!"

        client_sock.send(req + "\n")
    except Exception as e:
        logging.error("Error occured while sending sensors values to the client : %s", e)
    finally:
        if conn:
            conn.close()

# Sends the sensors status to the client
# client_sock : client socket
def sendSensorsStatus(client_sock):
    logging.info("Sending sensors status to client...")
    client_sock.send("sensors#" + str(bs_utils.active_sensors) + "#" + str(bs_utils.inactive_sensors) + "\n")

# Handles the client requests
# data : client requests
# client_sock : client socket (used to reply)
def handleRequest(data, client_sock):
    datasplit = data.rstrip().split("#")
    logging.info("Received from client : %s", data.rstrip())
    try:
        if(len(datasplit) > 1):
            if(datasplit[1] == "mail"):
                sendMail(datasplit[2], datasplit[3])
            if(datasplit[1] == "automail"):
                enableAutoMailProcess(datasplit[2], datasplit[3])
            if(datasplit[1] == "connect"):
                wifiConnect(datasplit[2], datasplit[3])
            if(datasplit[1] == "get"):
                sendSensorsValues(client_sock, datasplit[2])
            if(datasplit[1] == "sensors"):
                sendSensorsStatus(client_sock)
            if(datasplit[1] == "types"):
                sendSensorsTypes(client_sock)
            if(datasplit[1] == "shutdown"):
                logging.info("Shutting down...")
                while(bs_utils.db_process):
                    time.sleep(0.100)
                os.system("sudo shutdown -h now")
    except Exception as e:
        logging.error("Error occured from client : %s", e)

# Opens a Bluetooth socket to listen to the mobile app
def server():
    logging.info("Starting bluetooth server...")
    os.system("sudo hciconfig hci0 piscan")
    server_sock = BluetoothSocket(RFCOMM)
    server_sock.bind(("",PORT_ANY))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]
    advertise_service( server_sock, "BlueService",
                    service_id = bs_utils.server_uuid,
                    service_classes = [bs_utils.server_uuid, SERIAL_PORT_CLASS],
                    profiles = [SERIAL_PORT_PROFILE])

    while True:
        logging.info("Waiting for connection on RFCOMM")
        client_sock, client_info = server_sock.accept()

        logging.info("Accepted connection from %s", client_info)
        client_sock.send("RPI\n")
        try:
            while True:
                data = client_sock.recv(1024)
                if len(data) == 0 : 
                    break
                else :
                    handleRequest(data.decode("utf-8"), client_sock)
        except IOError:
            pass

        logging.info("Client disconnected")
        client_sock.close()
