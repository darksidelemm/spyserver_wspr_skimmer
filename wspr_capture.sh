#!/usr/bin/env bash
#
#   WSPR Splitter Script
#
# USB Frequency, in Hz
# 160m = 1836600
# 80m = 3568600
# 40m = 7038600
# 30m = 10138700
# 20m = 14095600
# 17m = 18104600
# 15m = 21094600
# 12m = 24924600
# 10m = 28124600
FREQ=14095600

# SpyServer Details
HOST=localhost
PORT=5555

# Working Directory
# Default = RPi Ramdisk area
OUTPUTDIR=/dev/shm/

#
# Start the demodulation chain
#
python3 wspr_splitter.py --hostname $HOST -p $PORT -f $FREQ -o $OUTPUTDIR