#!/usr/bin/python3

import socket, redis, time, logging
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from threading import Thread, Event

numShelves = 2					# Number of total shelves in server (incl. head)
updateFreq = 0.01				# Page update frequency in seconds
listenHost = "10.0.10.100"		# IP address of fanctl_disp
listenPort = 10000				# TCP port to listen on
head = "10.0.1.2"				# IP address of server system

# IP addresses of per-shelf fan controllers set automatically as 10.0.10.X where X is the shelf number
shelfIP = [""] * numShelves
for i in range(numShelves):
	shelfIP[i] = "10.0.10." + str(i)

# Set up flask and redis
logging.basicConfig(level=logging.WARNING)
app = Flask(__name__)
app.config['DEBUG'] = False
socketio = SocketIO(app, message_queue="redis://")
displayData = redis.Redis(host="localhost", port=6379, db=0)

# Set starting values for display info
displayData.set("hdd_temps","0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0")
displayData.set("cpu_temps","0 0 0 0 0 0 0 0")
displayData.set("cpu_fans","Fans 100% @ 1500 RPM;0")
for i in range(numShelves):
	displayData.set("shelf" + str(i),"Fans 100% @ 3000 RPM;00")

# Receive data from either server system or fan control systems in each shelf via socket connection
def getNewData(socket, displayData):
	MAX_LENGTH = 4096
	# Loop until connection is closed
	while 1:
		# Block at socket.recv until data is received; decode message as utf-8
		rcvBuffer = socket.recv(MAX_LENGTH).decode("utf-8")
		# Get peer IP to determine data source
		peerIP = socket.getpeername()[0]

		# If receive buffer is null, reset display data and return
		if rcvBuffer == '':
			if peerIP == head:
				displayData.set("hdd_temps","0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0")
			for i in range(numShelves):
				if peerIP == shelfIP[i]: displayData.set("shelf" + str(i),"DISCONNECTED!;0")
			return
		
		# If data is sent from head unit, determine the type of data based on leading tag (separated from data by ;)
		if peerIP == head:
			dataType = rcvBuffer.split(";",1)[0]
			data = rcvBuffer.split(";",1)[1]
			if dataType == "hdd":
				displayData.set("hdd_temps",data)
			elif dataType == "cpu":
				displayData.set("cpu_temps",data)
			elif dataType == "cpu_fans":
				displayData.set("cpu_fans",data)

		# If data is from shelf, update appropriate shelf data entry in redis DB
		for i in range(numShelves):
			if peerIP == shelfIP[i]: displayData.set("shelf" + str(i),rcvBuffer)

# Bind to display system IP/Port and listen for connections
def listen(displayData):
	serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

	# Attempt to bind to IP/port; keep retrying until it binds
	connected = False
	while connected == False:
		try:
			serverSocket.bind((listenHost, listenPort))
			serverSocket.listen(10)
			connected = True
		except:
			sleep(5)
			pass

	# Once bound, listen for incoming connections
	while 1:
		# Blocks at serverSocket.accept()
		(clientSocket, address) = serverSocket.accept()
		# Once connection is established, start a new thread to receive data and go back to listening for new connections
		getData = Thread(target=getNewData, args=(clientSocket,displayData,))
		getData.start()


# Send data from redis DB to jquery on web page via socket.io
def sendNewData(displayData):
	# Initialize all display data variables
	shelf = [""] * numShelves
	hdd_temps = ""
	cpu_temps = ""

	# Send data to web page every updateFreq seconds
	while 1:
		time.sleep(updateFreq)

		cpu_temps = displayData.get("cpu_temps").decode("utf-8")
		socketio.emit("cpuTempUpdate", {"cpu_temps": cpu_temps})

		cpu_fans = displayData.get("cpu_fans").decode("utf-8")
		socketio.emit("cpuFans", {"cpu_fans": cpu_fans})

		hdd_temps = displayData.get("hdd_temps").decode("utf-8")
		socketio.emit("hddTempUpdate", {"hdd_temps": hdd_temps})

		for i in range(numShelves):
			shelf[i] = displayData.get("shelf" + str(i)).decode("utf-8")
			socketio.emit("shelf", {"shelfData": str(i) + ";" + shelf[i]})

# Start thread to listen for new connections
sock = Thread(target=listen, args=(displayData,))
sock.start()

# Start thread to send updated data to web page
updateDisplay = Thread(target=sendNewData, args=(displayData,))
updateDisplay.start()

# Start flask/socket.io app
@app.route('/')
def index():
	return render_template('index.html')
if __name__ == '__main__':
	socketio.run(app, host='0.0.0.0', debug=False)
