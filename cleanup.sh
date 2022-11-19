#!/bin/bash
#
# Cleanup WSPR recordings older than 10 minutes.
#
find /dev/shm/WSPR* -mmin +10 -type f -exec rm -fv {} \;