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
# SpyServer Connection, requesting 12 kHz of IQ bandwidth, and using lots of buffering.
ss_iq -a 1200 -r $HOST -q $PORT -f $FREQ -s 12000 -b 16 - | \
# Convert the incoming signed 16-bit IQ to floating point
csdr convert_s16_f |\
# SSB demodulation using a tight bandpass filter (0-3600 Hz), and then taking the real part.
# (I could probably make this a bit narrower) Also add on some AGC and limiting.
csdr bandpass_fir_fft_cc 0 0.3 0.05 | csdr realpart_cf | csdr agc_ff | csdr limit_ff | \
# Convert back into signed 16-bit format and pass into wspr_splitter.py
csdr convert_f_s16 | python3 wspr_splitter.py -f $FREQ -o $OUTPUTDIR
