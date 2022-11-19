#!/usr/bin/env bash
#
#   WSPR Process Script
#

# Station information
CALLSIGN=N0CALL
GRID=PF95

# Working Directory
# Default = RPi Ramdisk area
OUTPUTDIR=/dev/shm/

# Log Output
WSPRLOG=wspr_decodes.txt

# Start decoder
python3 wspr_process.py -p $OUTPUTDIR -l $WSPRLOG $CALLSIGN $GRID