#!/usr/bin/env python
#
#   WSPR Decoder & Uploader
#   
#   Process files captured using wspr_splitter.py through k9an-wsprd, then
#   upload the results to wsprnet.
#
#   References:
#   - https://github.com/ve3gtc/uploadWspr/blob/master/uploadWspr.py
#   - https://github.com/lazywalker/DigiSkimmer/blob/master/digiskr/wsprnet.py
#
#   Mark Jessop <vk5qi@rfhead.net>
#
import argparse
import datetime
import glob
import logging
import os
import os.path
import re
import requests
import shutil
import subprocess
import sys
import time

from io import BytesIO


# Global Settings
UPLOADER_CALLSIGN = None
UPLOADER_GRID = None

PROCESS_PATH = "./"
PROCESS_MASK = "WSPR*.wav"

WSPRD_PATH = "wsprd"

LOG_OUTPUT = None

DONT_DELETE = False

REWRITE_DATETIME = True

WAIT_TIME = 10


# Storage of processed files in don't delete mode.
processed_files = []

# Instance of a regex to decode WSPR callsigns
wspr_splitter_pattern = re.compile("[<]?([A-Z0-9/]*)[>]?\s([A-R]{2}[0-9]{2}[\w]{0,2})\s([0-9]+)")


def get_file_info(filename):
    """
    Extract some information on a WSPR file capture from the filename. 

    Expected filename format is: WSPR_freqhz_YYYYMMDD-HHMMSS.wav
    
    """

    _basename = os.path.basename(filename)

    if _basename.startswith("WSPR") == False:
        return None

    try:
        _fields = _basename.split("_")

        _freq_hz = int(_fields[1])
        # Sanity check the frequency. Noting this upper limit might need to be modified for bands higher than 70cm!!
        if (_freq_hz < 0) or (_freq_hz > 500000000):
            logging.error(f"Frequency out of range: {_freq_hz}")
            return None

        # Attempt to parse the date/timestamp portion of the filename.
        # We can get this back into the WSPR format using  .strftime("%y%m%d %H%M")
        _datetime = datetime.datetime.strptime(_fields[2][:-4], "%Y%m%d-%H%M%SZ")

        return {'freq': _freq_hz, 'datetime': _datetime}
    
    except Exception as e:
        logging.error(f"Error parsing filename info from {filename} - {str(e)}")
        return None




def process_wspr(input, wsprd_path = WSPRD_PATH):
    """ Attempt to run an input file through wsprd, and return the output as an array of lines """
    # Check file exists.
    if os.path.isfile(input) is False:
        logging.error(f"Input file does not exist: {input}")
        return None
    

    # Get information from filename
    _file_info = get_file_info(input)
    if _file_info is None:
        return None
    
    # Parameters used:
    # -w = wideband search
    # -d = Deeper decode (takes longer)
    # -f <freq> - Set receiver dual frequency.
    _decoder_command = f"{wsprd_path} -w -d -f \"{_file_info['freq']/1e6:.5f}\" {input}"

    logging.debug(f"Running decoder command: {_decoder_command}")

    try:
        FNULL = open(os.devnull, "w")
        _start = time.time()
        ret_output = subprocess.check_output(_decoder_command, shell=True, stderr=FNULL)
        FNULL.close()
        ret_output = ret_output.decode("utf8")

    except subprocess.CalledProcessError as e:

        _runtime = time.time() - _start
        logging.debug(
            f"wsprd exited in {_runtime:.1f} seconds with return code {e.returncode}."
        )
        return None

    except Exception as e:
        # Something broke when running the decoder
        logging.error(
            f"Error when running wsprd - {sdr(e)}"
        )
        return None

    _runtime = time.time() - _start
    logging.debug(
        "wsprd exited in %.1f seconds." % _runtime
    )

    # Check for no output from dft_detect.
    if ret_output is None or ret_output == "":
        logging.debug("wsprd returned no output?")
        return None

    return {'raw_output': ret_output, 'freq': _file_info['freq'], 'datetime': _file_info['datetime']}


def process_wsprd_output(raw_output, spot_datetime):
    """
    Process and parse the raw output from wsprd.

    A lot of code from https://github.com/lazywalker/DigiSkimmer/blob/master/digiskr/wsjt.py
    """

    output = []

    for msg in raw_output.split("\n"):

        msg = msg.rstrip()

        # known debug messages we know to skip
        if msg.startswith("<DecodeFinished>"):  # this is what jt9 std output
            continue
        if msg.startswith(" EOF on input file"):  # this is what jt9 std output
            continue
        if msg == "":
            continue

        wsjt_msg = msg[29:].strip()
        spot = {
            #"timestamp": 
            "db": float(msg[5:8]),
            "dt": float(msg[9:13]),
            "freq": float(msg[14:24]),
            "drift": int(msg[25:28]),
            "mode": "WSPR",
            # FIXME: No idea what sync_quality used for but we need to add this field to bypass the upload check,
            # it seems to useless because the static files downloaded from wsprnet.org doesn't contain this field.
            # i don't want to read it from wspr_spots.txt so i simply pick a random value :)
            "sync_quality": 0.7,
            "msg": wsjt_msg,
        }

        m = wspr_splitter_pattern.match(wsjt_msg)
        if m is None:
            continue
        # TODO: handle msg type "<G0EKQ>        IO83PI 37"
        spot.update({"callsign": m.group(1), "locator": m.group(2), "watt": int(m.group(3))})

        # Convert back to the output format needed by WSPRnet
        mode = 2
        output.append("%s  %1.2f %d  %1.2f   %2.6f %s         %s   %d  %d  %d" % (
            # wsprnet needs GMT time
            spot_datetime.strftime("%y%m%d %H%M"),
            spot["sync_quality"],
            spot["db"],
            spot["dt"],
            # freq in MHz for wsprnet
            spot["freq"],
            spot["callsign"],
            spot["locator"],
            spot["watt"],
            spot["drift"],
            mode
        ))
        # 221009 0936   5 -10 -0.3 14.0970249  VK4TQ QG62 20          -1     1    0

    return output
        

def postprocess_spots(spots, spot_datetime):
    """ 
    Modify the date/time in each spot entry to match a supplied datetime.
    """

    output = []

    # Create the new datetime fields that will be updated in each spot.
    _new_datetime = spot_datetime.strftime("%y%m%d %H%M")

    for _spot in spots:
        # Catch any empty spots.
        if _spot == "":
            continue

        try:
            # Check this is a valid line
            _spot_date = _spot[:11]
            # This will break if the date is invalid
            _spot_datetime = datetime.datetime.strptime(_spot_date, "%y%m%d %H%M")

            # Update the datetime field.
            _new_spot = _new_datetime + _spot[11:]

            output.append(_new_spot)

        except Exception as e:
            logging.debug(f"Got invalid line in wsprd output.")
            continue

    return output


def upload_spots(spots, rx_callsign, rx_grid):
    """ Upload all received spots this cycle to WSPRnet """

    # Concatenate all spots together.
    spot_lines = ""
    for spot in spots:
        logging.debug("Spot Data: " + spot)
        spot_lines += spot + "\n"

    upload_data_bytes = spot_lines.encode()

    postfiles = {"allmept":  BytesIO(upload_data_bytes)}
    params = {"call": rx_callsign,
                "version": "spyserver_wspr_skimmer_v0.1",
                "grid": rx_grid}


    max_retries = 3
    retries = 0
    resp = None

    while True:
        try:
            requests.adapters.DEFAULT_RETRIES = 5
            s = requests.session()
            s.keep_alive = False
            resp = s.post("http://wsprnet.org/meptspots.php",
                            files=postfiles, params=params, timeout=300)

            if resp.status_code == 200:
                # if we can not find the text of success
                logging.debug("WSPRNet response: " + resp.text)
                break

        # TODO: handle with retry
        except requests.ConnectionError or requests.exceptions.Timeout as e:
            logging.error("Wsprnet connection error %s", e)
            if retries >= max_retries:
                logging.warning("Failed to upload.")
                break
            else:
                retries += 1
                logging.warning("wait 10s to try again...->%d", retries)
                time.sleep(10)
                continue
        except requests.exceptions.ReadTimeout as e:
            logging.error("Wsprnet read timeout error %s", e)
            break

    return





if __name__ == "__main__":

  # Command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "callsign",
        type=str,
        help=f"Uploader Callsign.",
    )
    parser.add_argument(
        "grid",
        type=str,
        help="Uploader Gridsquare",
    )
    parser.add_argument(
        "-p",
        "--path",
        default=PROCESS_PATH,
        type=str,
        help=f"Path to look for wav files. Default: {PROCESS_PATH}",
    )
    parser.add_argument(
        "-m",
        "--mask",
        default=PROCESS_MASK,
        type=str,
        help=f"File mask. Can be used to select a particular band. Default: {PROCESS_MASK}",
    )
    parser.add_argument(
        "-w",
        "--wsprd",
        default=WSPRD_PATH,
        type=str,
        help=f"Location of the k9an-wsprd binary. Default: {WSPRD_PATH}",
    )
    parser.add_argument(
        "-l",
        "--wspr_log",
        default=None,
        type=str,
        help=f"File to write WSPR log data to. Default: Disabled",
    )
    parser.add_argument(
        "-d", "--dont_delete", help="Don't delete files after processing.", action="store_true"
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
    WSPRD_PATH = args.wsprd
    PROCESS_PATH = args.path
    PROCESS_MASK = args.mask
    DONT_DELETE = args.dont_delete
    LOG_OUTPUT = args.wspr_log


    while True:

        current_spots = []

        _wav_files = glob.glob(os.path.join(PROCESS_PATH,PROCESS_MASK))

        if len(_wav_files) == 0:
            logging.debug("No new wav files, waiting.")
            time.sleep(WAIT_TIME)
            continue

        for _filename in _wav_files:
            # Don't re-process anything in the processed files list.
            if _filename in processed_files:
                continue

            # Attempt to decode any WSPR signals within the file.
            _wsprd_output = process_wspr(_filename, wsprd_path=WSPRD_PATH)

            if _wsprd_output is None:
                # No output, continue on.
                continue

            # Post-process any decoded spots, adding in the correct time.
            _spots = process_wsprd_output(_wsprd_output['raw_output'], _wsprd_output['datetime'])

            logging.debug(f"Got {len(_spots)} spots from {_filename}")

            for _spot in _spots:
                current_spots.append(_spot)

            # Either move on, or delete the file we just processed.
            if(DONT_DELETE):
                processed_files.append(_filename)
            else:
                os.remove(_filename)
                logging.debug(f"Deleted file: {_filename}")
        
        logging.info(f"Got {len(current_spots)} this cycle.")

        if(args.wspr_log):
            _logfile = open(args.wspr_log,'a')
            for _spot_line in current_spots:
                _logfile.write(_spot_line + "\n")
            _logfile.close()
            logging.debug("Wrote spots out to log file " + args.wspr_log)

        # Upload!
        if len(current_spots) > 0:
            upload_spots(current_spots, args.callsign, args.grid)
        
        logging.debug("Waiting for new files...")
        time.sleep(WAIT_TIME)




