# SpyServer WSPR Skimmer
Work-in-progress WSPR skimmer using a SpyServer connection.

A WSPR decoder/skimmer in two parts:
* A script (wspr_capture.sh) connects to a Spyserver using spyserver_client, demodulates SSB using csdr, then splits the received samples into 2-minute long wave files (aligned over the WSPR transmit periods) using wspr_splitter.py
* Another script periodically checks the output directory for new wave files, decodes these using wsprd and uploads spots to WSPRnet.

### Why am I writing this?
I run a cluster of [Airspy HF Discovery](https://airspy.com/airspy-hf-discovery/) receivers located at a low-noise remote site, with one Airspy unit per HF amateur radio band, all served up using multiple instances of [SpyServer](https://airspy.com/download/). Each spyserver instance can handle many client connections simultaneously, making them a good option for a remote high-performance HF receiver if you want to be able to have lots of simultaneous users.

While the SpyServer protocol is unfortunately partly closed (various 'special features' are reserved only for SDR#), there *are* open source clients for it, such as [SDR++](https://github.com/AlexandreRouma/SDRPlusPlus), and more useful to us, [spyserver_client](https://github.com/miweber67/spyserver_client) - a command-line client which can output IQ to stdout.

I'm already running multiple [HF APRS iGates](https://gist.github.com/darksidelemm/6b60767714295962771bca7b728b343c) hanging off these SpyServers, so why not run a WSPR skimmer too?

There's a heap of existing WSPR / other mode skimmer projects making use of KiwiSDRs (e.g. wsprdaemon, digiskimmer), and we do have KiwiSDRs located at the remote site, but I would prefer to devote those KiwiSDRs to public access rather than locking down channels to WSPR reception. Also, the receive performance of the Airspy Discovery units is better in some cases (in particular on the higher bands, where the fixed-gain KiwiSDRs becomes noise-figure limited).

Hence, this repository. I'm going to aim to keep things simple. No band hopping, just one connection to each spyserver, dumping files into a directory to be processed. Expansion to other modes (JT9?) *may* be possible, but that's for future me to worry about.

## TODO List
* Capture / Splitter
  * [x] Detection of dropped connection and restart. (Could be done by exiting when no samples, and just restarting the process?)
  * [ ] Long-term test of sample alignment - do we 'slip' over time?
  * [ ] Make script take input from environment variables for use in Docker container?

* Processing / Decoding
  * [x] Detection of new files.
  * [x] Run wsprd and collect output
  * [x] Actually process the output from 'mainline' wsprd, not a weird fork. DONE, without using regex...
  * [x] Detect errors from wsprd
  * [x] Post-process WSPR spots to update date/time
  * [x] Write WSPR spots to local file if enabled
  * [x] Batch upload spots to WSPRNet - Tentatively working?
  * [ ] Run decoders for multiple bands data in multiple processes. (Will this break the files that wsprd generates?)
  * [ ] Add command-line options for selecting deep decoding, and enabling of hash tables.
  * [ ] Figure out how to get wsprd to look for a hash table in a particular location, to avoid hash tables for different bands colliding.

* Docker Image


### Acknowledgements
This project wouldn't be possible without miweber67's [spyserver_client](https://github.com/miweber67/spyserver_client). This client has made getting IQ data from a SpyServer possible from the command-line, which allows many interesting possibilities.

[DigiSkimmer](https://github.com/lazywalker/DigiSkimmer) was a good reference for processing the output of wsprd, and uploading to WSPRnet (though it seems the 'MEPT' upload URL has changed.)


### Contacts
* [Mark Jessop](https://github.com/darksidelemm) - vk5qi@rfhead.net


## Dependencies
Full install instructions to come eventually I guess? For now here's what's needed to make this work.

Packages to install on a Raspbian installation:
```
$ sudo apt-get install vim git cmake build-essential wsjtx libsamplerate0-dev libfftw3-dev
```

### SpyServer Client

https://github.com/miweber67/spyserver_client

spyserver_client binary needs to be available on the system path as ss_iq
e.g.
```
$ git clone https://github.com/miweber67/spyserver_client.git
$ cd spyserver_client
$ make
$ sudo cp ss_client /usr/bin/ss_iq
```
(spyserver_client really needs a better makefile with an install target)

### CSDR
Original repo is abandoned, use https://github.com/jketterl/csdr.git

csdr binary needs to be available in the system path.

```
$ git clone https://github.com/jketterl/csdr.git
$ cd csdr
$ mkdir build
$ cd build
$ cmake ..
$ make
$ sudo make install
```

### WSPR Decoder
We need k9an-wsprd from the WSJT-X project. 

```
$ sudo apt-get install wsjtx
```


## Setup and Running
The provided scripts can be used to setup a WSPR capture and processing system.
By default all WSPR captures are saved to /dev/shm/, a RAMDisk setup by default on Raspbian installs.

```
$ git clone https://github.com/darksidelemm/spyserver_wspr_skimmer.git
```

* wspr_capture.sh - Connects to a spyserver using spyserver_client, demodulates USB, and writes out 2 minute files to disk.
* wspr_process.py - Process the 2-minute files through WSPR-Decoder, post-process the output, and upload to WSPRNet.

```
$ python3 wspr_process.py -p ./ -w ./wsprd -v MYCALL MYGRID
```


### Processing Service
Edit `wspr_process.sh` and update the CALLSIGN and GRID fields as appropriate.

Then, copy the wspr_process service file:
```
$ sudo cp wspr_process.service /etc/systemd/system/
$ sudo nano /etc/systemd/system/wspr_process.service
```
Edit /etc/systemd/system/wspr_process.service and update the paths (e.g. /home/pi) and User (pi) if not running from the pi user.

Start the processing service with:
```
$ sudo systemctl enable wspr_process
$ sudo systemctl start wspr_process
```

### Cleanup Cronjob
In-case the processing script dies for some reason, it's useful to have a cron-job to clean-up any unprocessed files.
The `cleanup.sh` script will delete any WSPR recordings in /dev/shm/ that are older than 10 minutes.

Edit your user crontab by running:
```
$ crontab -e
```
add the line:
```
*/30 * * * * /home/pi/spyserver_wspr_skimmer/cleanup.sh
```
(Changing the path if necessary)

### Capture Services
(Could probably done done in a cleaner way, with a larger bash script?)

The `wspr_capture.sh` script provides a template for setting up a capture process.
Copy this file, renaming it to include the band info, e.g.
```
$ cp wspr_capture.sh wspr_capture_20.sh
```
Edit the script to include the appropriate frequency, and SpyServer host and port information.

Then, copy the wspr_capture service file to /etc/systemd/system matching the script filename, e.g.
```
$ sudo cp wspr_capture.service /etc/systemd/system/wspr_capture_20.service
$ sudo nano /etc/systemd/system/wspr_capture_20.service
```

Edit the service file and update it to point to the appropriate script, e.g.:
```
ExecStart=/home/pi/spyserver_wspr_skimmer/wspr_capture_20.sh
```

Change the paths and User field if necessary.

Start the processing service with:
```
$ sudo systemctl enable wspr_capture_20
$ sudo systemctl start wspr_capture_20
```

Repeat the above for each band you wish to monitor.

### Checking Status
```
$ sudo tail -f /var/log/syslog | grep wspr
Nov 19 18:03:56 compute1 wspr_capture_30[8467]: 2022-11-19 18:03:56,797 INFO: Waiting for next start time: 20221119-073400Z
Nov 19 18:03:59 compute1 wspr_capture_30[8467]: 2022-11-19 18:03:59,876 INFO: Opened new temporary file: /dev/shm/temp_wspr_10138700.bin
Nov 19 18:03:59 compute1 wspr_capture_20[8454]: 2022-11-19 18:03:59,931 INFO: Opened new temporary file: /dev/shm/temp_wspr_14095600.bin
Nov 19 18:04:29 compute1 wspr_process[8164]: 2022-11-19 18:04:29,705 INFO: Got 23 this cycle.
Nov 19 18:05:56 compute1 wspr_capture_30[8467]: 2022-11-19 18:05:56,739 INFO: Reached 117 seconds, closed temporary file.
Nov 19 18:05:56 compute1 wspr_capture_30[8467]: 2022-11-19 18:05:56,740 INFO: Moved temporary file to: /dev/shm/WSPR_10138700_20221119-073400Z.wav
Nov 19 18:05:56 compute1 wspr_capture_30[8467]: 2022-11-19 18:05:56,740 INFO: Waiting for next start time: 20221119-073600Z
Nov 19 18:05:56 compute1 wspr_capture_20[8454]: 2022-11-19 18:05:56,778 INFO: Reached 117 seconds, closed temporary file.
Nov 19 18:05:56 compute1 wspr_capture_20[8454]: 2022-11-19 18:05:56,779 INFO: Moved temporary file to: /dev/shm/WSPR_14095600_20221119-073400Z.wav
Nov 19 18:05:56 compute1 wspr_capture_20[8454]: 2022-11-19 18:05:56,779 INFO: Waiting for next start time: 20221119-073600Z
Nov 19 18:06:00 compute1 wspr_capture_20[8454]: 2022-11-19 18:06:00,000 INFO: Opened new temporary file: /dev/shm/temp_wspr_14095600.bin
Nov 19 18:06:00 compute1 wspr_capture_30[8467]: 2022-11-19 18:06:00,005 INFO: Opened new temporary file: /dev/shm/temp_wspr_10138700.bin
```



## Development Notes

Decoding a wav file using wsprd:
```
./wsprd -H -w -f "14.0956" WSPR_14095600_20221009-094400Z.wav
400Z -20  0.6  14.097032  0  R0AGL NO67 10 
400Z  -9  1.5  14.097065  0  ZL1ZLD RF73 20 
400Z -23  6.5  14.097096  0  GI3VAF IO74 37 
400Z -19  0.4  14.097117  0  N8VZ EM89 23 
400Z -16  0.5  14.097129 -3  VK6BMT OF78 20 
400Z -12  0.5  14.097207  0  JA5FFO PM74 27 
<DecodeFinished>
```

The fields are: Time (broken), SNR, delta-time, frequency, drift, callsign, grid, tx_power
This has to be converted to a 'MEPT' format, for which the only documentation i've found is in various other codebases, which is awesome. This then gets uploaded to http://wsprnet.org/meptspots.php as a file attachment, with station information passed as parameters in the URL.

Documentation for wsprnet uploads seems to be basically non-existent in any place other than their arcane forums. I've had to dig through other codebases to figure out what is meant to be uploaded, and even then I'm not sure I'm doing it right.