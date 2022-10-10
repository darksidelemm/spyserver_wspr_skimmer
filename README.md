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
  * [ ] Detection of dropped connection and restart. (Could be done by exiting when no samples, and just restarting the process?)
  * [ ] Long-term test of sample alignment - do we 'slip' over time?
  * [ ] Make script take input from environment variables for use in Docker container?

* Processing / Decoding
  * [x] Detection of new files.
  * [x] Run wsprd and collect output
  * [x] Actually process the output from 'mainline' wsprd, not a weird fork. Refer here for parsing example: https://github.com/lazywalker/DigiSkimmer/blob/master/digiskr/wsjt.py#L272
  * [ ] Detect errors from wsprd
  * [x] Post-process WSPR spots to update date/time
  * [ ] Write WSPR spots to local file if enabled
  * [x] Batch upload spots to WSPRNet - Tentatively working?

* Docker Image


### Acknowledgements
This project wouldn't be possible without miweber67's [spyserver_client](https://github.com/miweber67/spyserver_client). This client has made getting IQ data from a SpyServer possible from the command-line, which allows many interesting possibilities.

[DigiSkimmer](https://github.com/lazywalker/DigiSkimmer) was a good reference for processing the output of wsprd, and uploading to WSPRnet (though it seems the 'MEPT' upload URL has changed.)


### Contacts
* [Mark Jessop](https://github.com/darksidelemm) - vk5qi@rfhead.net


## Dependencies
Full install instructions to come eventually I guess? For now here's what's needed to make this work.

### SpyServer Client

https://github.com/miweber67/spyserver_client

spyserver_client binary needs to be available on the system path as ss_iq
e.g.
```
$ sudo cp spyserver_client /usr/bin/ss_iq
```
(spyserver_client really needs a better makefile with an install target)

### CSDR
Original repo is abandoned, use https://github.com/jketterl/csdr.git

csdr binary needs to be available in the system path.

### WSPR Decoder
We need k9an-wsprd from the WSJT-X project. 

https://github.com/WSPRpi/WSPR-Decoder


## Running
Incomplete!

* wspr_capture.sh - Connects to a spyserver using spyserver_client, demodulates USB, and writes out 2 minute files to disk.

* wspr_process.py - Process the 2-minute files through WSPR-Decoder, post-process the output, and upload to WSPRNet.

```
$ python3 wspr_process.py -p ./ -w ./wsprd -v MYCALL MYGRID
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