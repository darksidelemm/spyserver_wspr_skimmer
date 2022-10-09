# SpyServer WSPR Skimmer

Work-in-progress WSPR skimmer using a SpyServer.


### Contacts
* [Mark Jessop](https://github.com/darksidelemm) - vk5qi@rfhead.net


## Dependencies

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

https://github.com/WSPRpi/WSPR-Decoder


## Running
Incomplete!

* wspr_capture.sh - Connects to a spyserver using spyserver_client, demodulates USB, and writes out 2 minute files to disk.
* TODO - Process the 2-minute files through WSPR-Decoder, post-process the output, and upload to WSPRNet.


## Notes

Decoding a wav file using wspr-decoder:
```
$ cat WSPR_14095600_20221009-093400Z.wav | ./k9an-wsprd -wf "14.0956" /dev/stdin

221009 0936   5 -10 -0.3 14.0970249  VK4TQ QG62 20          -1     1    0
221009 0936   2 -21 -0.4 14.0970327  R0AGL NO67 10           0   227    0
221009 0936   4 -10  0.6 14.0970642  ZL1ZLD RF73 20          0     2    0
221009 0936   2 -19  1.8 14.0970784  F1JSC JN03 37          -1  1193   -3
...
```

The output from k9an-wsprd assumes the current system time, which isnt always valid in this case.
Will need to modify the timestamp at the start of each line to match the timestamp in the filename.

