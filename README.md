# FreeNAS-Fan-Control
Fan control system for multi-chassis FreeNAS systems, including a display webserver

The script in the Primary Control Script directory runs on the FreeNAS system itself and is started on init.

The script in the Client Script directory runs on each rpi in each shelf. They're loaded as systemd services that restart upon errors.

The stuff in the Display Script directory makes the webserver work. It uses flask, socket.io, and redis.

More information can be found on http://jro.io/nas#expansion
