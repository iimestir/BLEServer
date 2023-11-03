import os

# Upgrading packages
os.system("sudo apt-get update")

# Dependencies installation
os.system("sudo apt-get install --reinstall -y bluetooth")
os.system("sudo apt-get install --reinstall -y libbluetooth-dev")
os.system("sudo apt-get install --reinstall -y bluez")

# Python Libraries installation
os.system("sudo pip3 install wifi")
os.system("sudo pip3 install pybluez")
os.system("sudo pip3 install bluepy")
os.system("sudo pip3 install influxdb")
os.system("sudo pip3 install XlsxWriter")
os.system("sudo pip3 install pytz")
os.system("sudo pip3 install tzlocal")
os.system("sudo pip3 install numpy")

# Server Installation & Compilation
os.system("sudo mkdir -p /usr/bin/BlueServer")
os.system("sudo tar -xf BlueServer.tar -C /usr/bin/BlueServer/")
os.system("sudo wget http://www.cooking-hacks.com/media/cooking/images/documentation/raspberry_arduino_shield/raspberrypi2.zip")
os.system("unzip raspberrypi2.zip")
os.system("cd cooking/arduPi && sudo chmod a+x install_arduPi && ./install_arduPi && rm install_arduPi && cd ../..")
os.system("sudo rm raspberrypi2.zip")
os.system("sudo g++ -c lora/libs/*.h lora/libs/*.hpp lora/libs/*.cpp")
os.system("sudo mv *.o lora/libs/")
os.system("sudo g++ lora/libs/*.o lora/lora_sender.cpp -o /usr/bin/BlueServer/lora_sender -lpthread")
os.system("sudo touch /usr/bin/BlueServer/lora")
os.system("sudo touch /usr/bin/BlueServer/keys")

# Configuration
content = ""
with open('/etc/systemd/system/dbus-org.bluez.service','r') as f:
    for line in f:
        if(line.strip() == "ExecStart=/usr/lib/bluetooth/bluetoothd"):
            content += line.strip() + " -C\n"
        else:
            content += line.strip() + "\n"
with open('/etc/systemd/system/dbus-org.bluez.service','w') as f:
    f.write(content)

# Services creation
blueservice = """[Unit]
Description=BlueServer
After=multi-user.target
Conflicts=getty@tty1.service

[Service]
Type=simple
WorkingDirectory=/usr/bin/BlueServer
ExecStart=sudo /usr/bin/python3 /usr/bin/BlueServer/BlueServer.py
StandardOutput=tty-force

[Install]
WantedBy=multi-user.target"""
with open('/etc/systemd/system/BlueServer.service','w') as f:
    f.write(blueservice)

loraservice = """[Unit]
Description=Send every datas present in data.txt file
After=networking.service
StartLimitIntervalSec=10

[Service]
Type=simple
Restart=always
RestartSec=1
User=root
UMask=777
ExecStart=/usr/bin/BlueServer/lora_sender
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
with open('/etc/systemd/system/lora_sender.service','w') as f:
    f.write(loraservice)

os.system("sudo systemctl enable BlueServer.service")
os.system("sudo systemctl enable lora_sender.service")

# Reload & Reboot
os.system("sudo systemctl daemon-reload")
os.system("sudo sdptool add SP")
os.system("sudo reboot")