#!/usr/bin/python3

import pigpio, time, socket, os, subprocess, signal, sys, datetime
from threading import Thread

# Set up log file
log_file = "/home/ctl/logs/fanctl.log"
log = open(log_file,'w')
sys.stdout = log
sys.stderr = log

# PWM output setup
pi = pigpio.pi()
pi.set_mode(3, pigpio.OUTPUT)
pi.set_PWM_frequency(3,25000)
pi.set_PWM_range(3,100)
pi.set_PWM_dutycycle(3,100)

# RPM input setup
pi.set_mode(2, pigpio.INPUT)
pi.set_pull_up_down(2, pigpio.PUD_UP)
halfRevs = pi.callback(2)

# Temperature input setup
os.system("modprobe w1-gpio")
os.system("modprobe w1-therm")
sensor_id = subprocess.check_output("ls /sys/bus/w1/devices/ | grep 28-",shell=True).decode("utf-8").replace("\n","")
temp_sensor = "/sys/bus/w1/devices/" + sensor_id + "/w1_slave"

# Global vars
global dutyCycle, oldDuty, ramp, cycleUpdate
dutyCycle = 100
oldDuty = dutyCycle
ramp = dutyCycle
cycleUpdate = False

# Timestamps
rpm_t1 = time.time()
rpm_tDutyChange = rpm_t1
pwm_t1 = rpm_t1
temp_t1 = rpm_t1
connect_t1 = rpm_t1

# User vars
rpmFreq = 1
tempFreq = 10
rampSpeed = 1

# RPM limits
highLimit = 100
lowLimit = 0

# Once we get a socket connection, this processes the data it sends.
def handle(socket):
	global dutyCycle, oldDuty, ramp, cycleUpdate
	MAX_LENGTH = 4096
	print(datetime.datetime.today().strftime('%m-%d-%Y %H:%M:%S') + " - ", end = "")
	print("Client connected!",flush=True)

	# Continually loop while we have a connection
	while 1:
		# Process received data. This blocks further execution, so nothing below will run until we get new data here.
		rcvBuffer = socket.recv(MAX_LENGTH).decode("utf-8")

		# If we got new data, but it's NULL, the client disconnected. Exit function.
		if rcvBuffer == '':
			print(datetime.datetime.today().strftime('%m-%d-%Y %H:%M:%S') + " - ", end = "")
			print("Client closed connection!",flush=True)
			return
		try:
			# rcvBuffer should contain a number, 0 to 100, that indicates the desired duty cycle. Correct for out of bounds values.
			rcvBuffer = int(rcvBuffer)
			if rcvBuffer > highLimit: rcvBuffer = highLimit
			if rcvBuffer < lowLimit: rcvBuffer = lowLimit
		except:
			# Correct for any corrupt (non-numerical, etc) values received
			rcvBuffer = dutyCycle
			pass

		# If we're in the middle of a duty cycle ramp, the current ramp value becomes the old duty cycle
		if cycleUpdate == True:
			oldDuty = ramp
		else:
			# If not, start a duty cycle ramp by storing the original duty cycle
			oldDuty = dutyCycle
			ramp = dutyCycle

		# Set the desired duty cycle value and mark that we need to update our duty cycle output
		dutyCycle = int(rcvBuffer)
		cycleUpdate = True

# This function listens for incoming socket connections. Once it gets a connection, it spins off a new thread to handle the communication
# and goes back to listening for new connections.
def listen():
	# Get the current private IP address of the this host by connecting to some server and checking the socket IP address. This is an easy
	# way for me to tell which controller is which; their addresses are statically assigned, so I can look at their IP to see if they're in
	# the head unit, shelf 1, etc. This lets me use the same exact script on both devices without having to change some global variable at
	# the top to switch "modes" between the head unit, shelf 1, etc etc.
	temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	temp_sock.connect(("8.8.8.8", 80))
	client_ip = temp_sock.getsockname()[0]
	temp_sock.close()

	# Listen on the internal IP we detected above at port 10000
	serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	PORT = 10000
	HOST = client_ip
	serversocket.bind((HOST, PORT))
	serversocket.listen(10)

	# Continually listen. The first line blocks. Once we get a connection, start a new thread with the socket handle function and go back
	# to listening for new connections.
	while 1:
		(clientSocket, address) = serversocket.accept()
		ct = Thread(target=handle, args=(clientSocket,))
		ct.start()

# Read the temperature data from the attached thermal probe
def read_temp():
	# The temperature sensor is a file in /sys/bus/w1/devices/. Read that file and close it.
	probe = open(temp_sensor, 'r')
	lines = probe.readlines()
	probe.close

	# Check if the output is valid. If not, attempt to read the file again.
	while lines[0].strip()[-3:] != 'YES':
		time.sleep(0.2)
		probe = open(temp_sensor, 'r')
		lines = probe.readlines()
		probe.close

	# Locate the actual temperature data from the output
	temp_output = lines[1].find('t=')

	# If the output is sane, convert it to F and return the value as a string
	if temp_output != -1:
		temp_string = lines[1].strip()[temp_output+2:]
		temp = float(temp_string) / 1000.0 * 9.0 / 5.0 + 32.0
		return str(int(temp))
	else:
		return 0

# Stuff to run when the script stops from SIGTERM
def close_client(signum, frame):
	callback.cancel()
	GPIO.cleanup()
	pi.stop()

signal.signal(signal.SIGTERM,close_client)

# Start the socket listening function in a new thread
sock = Thread(target=listen)
sock.start()

# Read the ambient temp for the first time
ambTemp = read_temp()

# Set starting text for the display
displayText = "Fans @ 100%;0"
rpms = "0"

# Set up pre-connection stuff for socket connection w/ display
connectedToDisplay = False
sock_display = socket.socket()

# Loop continually
while 1:
	# If we aren't connected to the display (as we won't be when this first runs), attempt to connect
	if connectedToDisplay == False:
		connect_t2 = time.time()
		if connect_t2 - connect_t1 > 5:
			try:
				sock_display.connect(("10.0.10.100", 10000))
				print(datetime.datetime.today().strftime('%m-%d-%Y %H:%M:%S') + " - ", end = "")
				print("Connected to display at " + sock_display.getpeername()[0],flush=True)
				connectedToDisplay = True
			except:
				print(datetime.datetime.today().strftime('%m-%d-%Y %H:%M:%S') + " - ", end = "")
				print("Connection error with display, trying again in 5 sec",flush=True)
				connect_t1 = connect_t2
				pass

	# Detect if the duty cycle ramp is finished. If it is, stop the ramp and reset the RPM tick tally
	if cycleUpdate == True and (ramp == dutyCycle or oldDuty == dutyCycle):
		cycleUpdate = False
		rpm_tDutyChange = rpm_t2
		halfRevs.reset_tally()

	# This stuff was ported directly from the arduino code that didn't support threading, so it's implemented
	# in kind of a dumb way currently. As the thing is looping, it checks the timestamp over and over and if 
	# enough time has elapsed, it does whatever action is inside the if statement. This first one runs every
	# tempFreq seconds (10 by default) and reads the ambient temperature.
	temp_t2 = time.time()
	if temp_t2 - temp_t1 >= tempFreq:
		ambTemp = read_temp()
		temp_t1 = temp_t2

	# This one runs every rpmFreq seconds (1 by default) and calculates the fan RPMs. It runs a rolling average
	# that keeps going until the next duty cycle update (otherwise the value tends to bounce around a lot)
	rpm_t2 = time.time()
	if rpm_t2 - rpm_t1 >= rpmFreq:
		ticks = halfRevs.tally()
		rpms = str(int(ticks / (rpm_t2 - rpm_tDutyChange) / 2 * 60))
		rpm_t1 = rpm_t2

	# This runs every rampSpeed seconds (1 by default) and bumps the duty cycle up or down one tick if we're in
	# the middle of a duty cycle ramp. If we're not in a duty cycle ramp, this gets skipped.
	pwm_t2 = time.time()
	if cycleUpdate == True and pwm_t2 - pwm_t1 >= rampSpeed:
		if oldDuty < dutyCycle: ramp += 1
		if oldDuty > dutyCycle: ramp -= 1
		pi.set_PWM_dutycycle(3,ramp)
		pwm_t1 = pwm_t2

	# Sends updated data to the display, including fan duty cycle, RPM, and ambient temp
	displayText_old = displayText
	if cycleUpdate == True:
		# If we're in the middle of a ramp, show the old duty cycle, the new duty cycle, the current ramp value, and temperature
		displayText = "Fans " + str(ramp) + "% (" + str(oldDuty) + "% -> " + str(dutyCycle) + "%);" + ambTemp
	else:
		# If we're not in a ramp, just show current duty cycle, rpm, and temperature
		displayText = "Fans " + str(dutyCycle) + "% @ " + rpms + " RPM;" + ambTemp
	# Attempt to send the data to the display. If we can't, set the "connectedToDisplay" value to False so we attempt to reconnect next loop.
	# We don't want our PWM updates to stop because we can't connect to the display, so this is set up to not block.
	if displayText_old != displayText:
		try:
			sock_display.send(displayText.encode("utf-8"))
		except:
			print(datetime.datetime.today().strftime('%m-%d-%Y %H:%M:%S') + " - ", end = "")
			print("Not connected to display web socket!",flush=True)
			connectedToDisplay = False
			sock_display.close()
			sock_display = socket.socket()
			pass