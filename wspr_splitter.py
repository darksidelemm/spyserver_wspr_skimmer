#!/usr/bin/env python
#
#   WSPR Splitter
#   
#	Proof-of-concept code to take a stream of input samples, and write out
#   time-bounded wave files for WSPR decoding.
#
#   Input samples must be signed 16-bit little-endian format. No WAV header required.
#
#   Mark Jessop <vk5qi@rfhead.net>
#
import argparse
import datetime
import logging
import os
import shutil
import sys
import time
import wave
from threading import Thread
from spyserver_client import USBDemod

# Global parameters which will be over-written by command-line options
# Receive frequency, in Hz (used in the output filename)
RX_FREQ = 14095600

# Input sample format information
SAMPLE_RATE = 12000
SAMPLE_WIDTH = 2

TEMPORARY_FILE = "temp_wspr.bin"
OUTPUT_PATH = "./"

# Threshold for splitting files.
TIME_THRESHOLD = 0.2

# Collection length (<120 second WSPR time window)
COLLECT_LENGTH = 117


# Timeot
DATA_TIMEOUT = 10

# Last data time
last_data = time.time()

# USB Demodulator object
usb_demod = None


def round_time(dt=None, date_delta=datetime.timedelta(minutes=2), to='up'):
    """
    Round a datetime object to a multiple of a timedelta
    dt : datetime.datetime object, default now.
    dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
    from:  http://stackoverflow.com/questions/3463930/how-to-round-the-minute-of-a-datetime-object-python
    """
    round_to = date_delta.total_seconds()
    if dt is None:
        dt = datetime.now()
    seconds = (dt - dt.min).seconds

    if seconds % round_to == 0 and dt.microsecond == 0:
        rounding = (seconds + round_to / 2) // round_to * round_to
    else:
        if to == 'up':
            # // is a floor division, not a comment on following line (like in javascript):
            rounding = (seconds + dt.microsecond/1000000 + round_to) // round_to * round_to
        elif to == 'down':
            rounding = seconds // round_to * round_to
        else:
            rounding = (seconds + round_to / 2) // round_to * round_to

    return dt + datetime.timedelta(0, rounding - seconds, - dt.microsecond)


def get_next_start_datetime():
    """ Return a datetime of the next WSPR transmission start time """
    _now = datetime.datetime.utcnow()
    # Round current time up to the next 2 minute boundary.
    return round_time(_now, date_delta=datetime.timedelta(minutes=2), to='up')


def watchdog_thead():
    global last_data, usb_demod

    while True:
        if (time.time() - last_data) > DATA_TIMEOUT:
            logging.critical(f"No incoming data for {DATA_TIMEOUT} seconds. Exiting and re-starting,")
            # Kill this process the harsh way, to be sure it exits.
            usb_demod.close()
            os._exit(1)
        
        time.sleep(1)

if __name__ == "__main__":

  # Command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hostname",
        default="localhost",
        type=str,
        help=f"SpyServer Hostname. Default: localhost",
    )
    parser.add_argument(
        "-p",
        "--port",
        default=5555,
        type=int,
        help=f"SpyServer Port. Default: 5555",
    )
    parser.add_argument(
        "-f",
        "--rx_freq",
        default=RX_FREQ,
        type=int,
        help=f"Receive Frequency (Hz). Default: {RX_FREQ}",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        default="./",
        help="Output Directory. Default: ./",
    )
    parser.add_argument(
        "-r",
        "--sample_rate",
        default=SAMPLE_RATE,
        type=int,
        help=f"Audio Sample Rate (Hz). Must be S16LE format. Default: {SAMPLE_RATE}",
    )
    parser.add_argument(
        "-l",
        "--collect_length",
        type=int,
        default=COLLECT_LENGTH,
        help=f"Collection Length (seconds). Default: {COLLECT_LENGTH}",
    )
    parser.add_argument(
        "-v", "--verbose", help="Enable debug output.", action="store_true"
    )
    args = parser.parse_args()

    # Set log-level to DEBUG if requested
    if args.verbose:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    # Set up logging
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging_level)

    # Write in Arguments
    RX_FREQ = args.rx_freq
    SAMPLE_RATE = args.sample_rate
    COLLECT_LENGTH = args.collect_length
    OUTPUT_PATH = args.output_dir
    TEMPORARY_FILE = OUTPUT_PATH + f"temp_wspr_{RX_FREQ}.bin"
    MAX_COLLECT_SAMPLES = COLLECT_LENGTH*SAMPLE_RATE


    # Start SSB Demodulator
    usb_demod = USBDemod(
        hostname=args.hostname,
        port=args.port,
        frequency=args.rx_freq,
        sample_rate=args.sample_rate
    )

    _next_start = get_next_start_datetime()

    _current_file = None
    _current_filename = ""
    _current_samples = 0

    # WAITING -> COLLECTING
    _state = "WAITING"

    logging.info("Waiting for next start time: " + _next_start.strftime("%Y%m%d-%H%M%SZ"))

    # Start Watchdog thread.
    watchdog = Thread(target=watchdog_thead)
    watchdog.start()

    while True:
        # Read in 0.1 seconds of samples at a time.
        _data = usb_demod.read(int(SAMPLE_RATE*SAMPLE_WIDTH*0.1)) 

        if _data == b'':
            # No data means STDIN has closed. Bomb out here.
            logging.error("stdin closed, exiting.")
            usb_demod.close()
            os._exit(1)
        
        # Update timer
        last_data = time.time()

        _time_delta = abs((datetime.datetime.utcnow() - _next_start).total_seconds())


        if _state == "WAITING":
            # Waiting for the next start time.


            if ( _time_delta < TIME_THRESHOLD ):
                # Time to start a new file.
                # Close the current file
                if _current_file:
                    logging.info("Closed file: "+ _current_filename)
                    _current_file.close()

                # Generate new filename.
                _current_filename = OUTPUT_PATH + f"WSPR_{RX_FREQ}_" + _next_start.strftime("%Y%m%d-%H%M%SZ") + ".wav" 
                
                _current_file = wave.open(TEMPORARY_FILE, 'wb')
                _current_file.setnchannels(1)
                _current_file.setsampwidth(SAMPLE_WIDTH)
                _current_file.setframerate(SAMPLE_RATE)

                logging.info("Opened new temporary file: " + TEMPORARY_FILE)
                _state = "COLLECTING"
                _next_start = get_next_start_datetime()


            elif (_time_delta > 200):
                # Somehow missed a start time by a huge amount, try and get the next one.
                _next_start = get_next_start_datetime()
                # Discard incoming data
                continue
            
            else:
                # Discard data
                continue

        if _state == "COLLECTING":

            if (_current_file):
                _current_file.writeframesraw(_data)

                _current_samples += len(_data)//2

                logging.debug(f"Current collection time: {(_current_samples/SAMPLE_RATE):.1f} / {COLLECT_LENGTH}")

                if (_current_samples >= (MAX_COLLECT_SAMPLES)):
                    # Finished our recording, close.
                    logging.info(f"Reached {COLLECT_LENGTH} seconds, closed temporary file.")
                    _current_file.close()
                    _current_file = None
                    _current_samples = 0
                    
                    # Move file to destination filename.
                    try:
                        shutil.move(TEMPORARY_FILE, _current_filename)
                        logging.info(f"Moved temporary file to: "+ _current_filename)
                    except Exception as e:
                        logging.error(f"Error moving temporary file {TEMPORARY_FILE}: " + str(e))

                    _next_start = get_next_start_datetime()
                    _state = "WAITING"
                    logging.info("Waiting for next start time: " + _next_start.strftime("%Y%m%d-%H%M%SZ"))

            else:
                _state = "WAITING"



