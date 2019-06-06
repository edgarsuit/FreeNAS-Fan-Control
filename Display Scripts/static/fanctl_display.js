$(document).ready(function(){
	var num_chassis = 2;	// Total number of chassis
	var num_drives = 40;	// Total number of drives in all chassis
	var num_threads = 8;	// Number of logical CPU threads

	// Connect to socket.io running in the Python script
	var socket = io.connect('http://' + document.domain + ':' + location.port);

	// jQuery function for updating the CPU temperature values
	socket.on('cpuTempUpdate', function(msg) {
		// Set up variables for processing data
		var temps = new Array(num_threads);
		var top_temp = 0;
		var hot_threads = new Array(num_threads);

		// Data will come in as as space delineated list, split this into array and find the highest temp
		for (var i = 0; i < num_threads; i++) {
			temps[i] = msg.cpu_temps.split(" ")[i];
			temp = parseInt(temps[i]);
			if (temp > top_temp) { top_temp = temp; }
		}

		// Go back through array and find if multiple cores are the same (top) temp
		for (var i = 0; i < num_threads; i++) {
			if (parseInt(temps[i]) == top_temp) {
				hot_threads.push(i)
			}
		}

		// Set the cell values to the temp values and add html class data to hottest cores to color them red
		for (var i = 0; i < temps.length; i++){
			$('#cpu' + (i+1).toString()).html(temps[i] + "°C");
			if (hot_threads.indexOf(i) != -1) {
				$('#cpu' + (i+1).toString()).addClass("hot");
			} else {
				$('#cpu' + (i+1).toString()).removeClass("hot");
			}
		}
	});

	// jQuery function for updating the CPU fan speed values
	socket.on('cpuFans', function(msg) {
		// Parse the data from the incoming message (separated by ;)
		var cpuFanSpeed = msg.cpu_fans.split(";")[0]
		var cpuPercent = msg.cpu_fans.split(";")[1]

		// Send the data to the html doc
		$('#cpuFanSpeed').html(cpuFanSpeed);
		$('#cpuPercent').html("CPU @ " + cpuPercent + "%");
	});

	// jQuery function for updating the HDD temp values
	socket.on('hddTempUpdate', function(msg) {
		// Set up variables for processing data
		var temps = new Array(num_drives);
		var top_temp = [0,0];
		var hot_disks = new Array(num_drives);

		// Find hottest disk per shelf
		for (var i = 0; i < num_drives; i++) {
			temps[i] = msg.hdd_temps.split(" ")[i];
			temp = parseInt(temps[i]);
			if (i < 24) {
				if (temp > top_temp[0]) { top_temp[0] = temp; }
			} else {
				if (temp > top_temp[1]) { top_temp[1] = temp; }
			}
		}

		// Find if multiple disks per shelf are the same hottest temp
		for (var i = 0; i < num_drives; i++) {
			if (i < 24) {
				if (parseInt(temps[i]) == top_temp[0]) {
					hot_disks.push(i);
				}
			} else {
				if (parseInt(temps[i]) == top_temp[1]) {
					hot_disks.push(i);
				}
			}
		}

		// Send all temp data to the table, color cells with hottest drives red by adding html class to the cell
		for (var i = 0; i < temps.length; i++){
			$('#disk' + (i+1).toString()).html(temps[i] + "°C");
			if (hot_disks.indexOf(i) != -1) {
				$('#disk' + (i+1).toString()).addClass("hot");
			} else {
				$('#disk' + (i+1).toString()).removeClass("hot");
			}
		}
	});

	// jQuery function for updating the HDD fan and ambient temp values
	socket.on('shelf', function(msg) {
		// Split the data out per shelf
		var shelfNum = msg.shelfData.split(";")[0]
		var fanSpeed = msg.shelfData.split(";")[1]
		var ambTemp = msg.shelfData.split(";")[2]

		// Send to html doc for display
		$('#fanSpeed' + shelfNum).html(fanSpeed);
		$('#ambTemp' + shelfNum).html("Amb. " + ambTemp + "°F");
	});
});