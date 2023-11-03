# Mails module

import logging
import time
import threading
import smtplib
import os
import multiprocessing
import sqlite3
import bs_utils
from bs_utils import auto_mail_process, getBTName, getDate
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from sqlite3 import Error
from xlsxwriter.workbook import Workbook
import configparser

# Used to send a mail with X days of data
# mail : e-mail address
# days : number of days of data to send
def sendMail(mail, days):
    first_date = getDate(days)
    last_date = getDate(0)
    
    if(first_date == "" or first_date == None or last_date == "" or last_date == None):
        logging.error("No valid data found while sending the mail")
        return
    
    try:
        if(days < 1 or days > 60):
            logging.error("Invalid day registered")
            return

        if(convertToXLSX(days) == False):
            logging.error("Failed to convert the database to an xlsx")
            return

        if("@" in mail and "." in mail.split("@")[1]):
            logging.info("Sending mail to : %s", mail)
        else :
            logging.error("Invalid mail")
            return

        msg = MIMEMultipart()
        msg['From'] = bs_utils.sender_mail
        msg['To'] = mail
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = "Données des capteurs du magasin : " + datetime.today().strftime('%d/%m/%Y')

        part = MIMEBase('application', "octet-stream")
        part.set_payload(open("sensors_"+getBTName()+".xlsx", "rb").read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="sensors_'+getBTName()+'.xlsx"')

        msg.attach(MIMEText("Bonjour,\n\n" + 
        "Vous trouverez joint à ce mail les données des capteurs récoltées du "+first_date+" au "+last_date+"\n\n"+ 
        "Veuillez ne pas répondre à ce mail.\n\n" +
        "-Bien à vous."))
        msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(bs_utils.sender_mail, bs_utils.sender_pass)
        server.sendmail(bs_utils.sender_mail, mail, msg.as_string())
        server.close()
    except Exception as e:
        logging.error("%s", e)
    finally:
        if(os.path.exists("sensors_"+getBTName()+".xlsx")):
            os.remove("sensors_"+getBTName()+".xlsx")

# Used to convert a DB to an .xlsx file
# days : number of days of values that will be registered in the xlsx file
def convertToXLSX(days):
    try:
        workbook = Workbook('sensors_'+getBTName()+'.xlsx')
        worksheet = workbook.add_worksheet()
        conn = sqlite3.connect("sensors.db")
        c = conn.cursor()
        query = "SELECT * FROM("
        query += "SELECT * FROM sensors"
        query += " WHERE " + bs_utils.date_time + " BETWEEN DATETIME('now','localtime','-"+str(days)+" days') AND DATETIME('now','localtime')"
        query += " ORDER BY " + bs_utils.date_time
        query += ")"
        query += " ORDER BY " + bs_utils.date_time + " ASC"
        c.execute(query)
        records = c.fetchall()
        measurement = [description[0] for description in c.description]

        for i in range(len(measurement)):
            worksheet.set_column(0, i, 20)
            worksheet.write(0, i, str(measurement[i]))

        for i in range(len(records)):
            for j in range(len(records[i])):
                worksheet.write(i+1, j, records[i][j])

        if conn:
            conn.close()
        workbook.close()

        return True
    except Exception as e:
        logging.error(e)
        if conn:
            conn.close()
        workbook.close()
        
        return False

# Used to send a mail cyclically
# mail : e-mail address
# freq : frequency (in days)
def cyclicMail():
    mail = None
    days = 0

    config = configparser.ConfigParser()
    try:
        config.read("config.cfg")
        if(config.get("MAIL", "mail") != "null" and config.get("MAIL", "freq") != "0"):
            logging.info("Activating auto-mail...")
            mail = config.get("MAIL", "mail")
            days = int(config.get("MAIL", "freq"))
    except Exception as e:
        logging.error("Error occured while starting automail process : %s", e)
        return

    if(mail == None):
        logging.error("Invalid mail, can't be 'None'")
        return
    if(days < 1):
        logging.warning("Invalid day, setting up its value to 1")
        days = 1
    if(days > 60):
        logging.warning("Invalid day, setting up its value to 60")
        days = 60

    while(True):
        time.sleep(days*86400)
        threading.Thread(target=sendMail, args=(mail, days,)).start()

# Starts the auto-mail cycle, used when the user send an automail request
# mail : user's mail
# freq : frequency (in days)
def enableAutoMailProcess(mail, freq):
    global auto_mail_process
    
    config = configparser.ConfigParser()
    try:
        config.read("config.cfg")
        if("MAIL" in config.sections()):
            config.set("MAIL", "mail", str(mail))
            config.set("MAIL", "freq", str(freq))
        else:
            config['MAIL'] = {"mail": str(mail),"freq": str(freq)}

        with open('config.cfg', 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        logging.error("Error occured while starting the auto mail process : %s", e)
        return

    startAutoMailProcess()

# Used at the start of the server.
# Reads the mail config file and starts a thread with the automail feature
def startAutoMailProcess():
    if(bs_utils.auto_mail_process != None):
        bs_utils.auto_mail_process.terminate()
    auto_mail_process = multiprocessing.Process(target=cyclicMail)
    auto_mail_process.start()