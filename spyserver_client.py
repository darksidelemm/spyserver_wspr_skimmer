#!/usr/bin/env python
#
#   SpyServer Client Wrapper
#
import logging
import os
import signal
import subprocess
import time
import traceback

from threading import Thread


class USBDemod(object):
    """
    Connect to a SpyServer using spyserver_client, and demodulate
    USB using CSDR.
    """

    def __init__(
        self,
        ss_iq_path = "ss_iq",
        csdr_path = "csdr",
        hostname = "localhost",
        port = 5555,
        frequency = 14094600,
        sample_rate = 12000,
        filter_high_pass = 300,
        filter_low_pass = 3000,
        filter_rolloff = 600,
        batch_size = 1200
    ):

        self.rx_process = None
    
        # ss_iq -a 1200 -r $HOST -q $PORT -f $FREQ -s 12000 -b 16 - | \
        # # Convert the incoming signed 16-bit IQ to floating point
        # csdr convert_s16_f |\
        # # SSB demodulation using a tight bandpass filter (0-3600 Hz), and then taking the real part.
        # # (I could probably make this a bit narrower) Also add on some AGC and limiting.
        # csdr bandpass_fir_fft_cc 0 0.3 0.05 | csdr realpart_cf | csdr agc_ff | csdr limit_ff | \
        # # Convert back into signed 16-bit format and pass into wspr_splitter.py
        # csdr convert_f_s16 

        _bandpass_low = filter_high_pass / float(sample_rate)
        _bandpass_high = filter_low_pass / float(sample_rate)
        _bandpass_rolloff = filter_rolloff / float(sample_rate)

        self.rx_command = f"{ss_iq_path} -a {int(batch_size)} -r {hostname} -q {int(port)} -f {int(frequency)} -s {int(sample_rate)} -b 16 | "
        self.rx_command += f"csdr convert_s16_f | csdr bandpass_fir_fft_cc {_bandpass_low:.3f} {_bandpass_high:.3f} {_bandpass_rolloff:.3f} | csdr realpart_cf | csdr agc_ff | csdr limit_ff | csdr convert_f_s16"

        logging.info(f"Starting RX with command: {self.rx_command}")
        # Start the thread.
        self.rx_process = subprocess.Popen(
            self.rx_command,
            shell=True,
            stdin=None,
            stdout=subprocess.PIPE,
            preexec_fn=os.setsid,
        ) 

    def read(self, nbytes):
        if self.rx_process:
            return self.rx_process.stdout.read(nbytes)
        else:
            return None


    def close(self):
        try:
            # Send a SIGKILL to the subprocess PID via OS.
            try:
                os.killpg(os.getpgid(self.rx_process.pid), signal.SIGKILL)

            except Exception as e:
                logging.debug("SIGKILL via os.killpg failed. - %s" % str(e))
            time.sleep(1)
            try:
                # Send a SIGKILL via subprocess
                self.rx_process.kill()
            except Exception as e:
                logging.debug("SIGKILL via subprocess.kill failed - %s" % str(e))

        except Exception as e:
            traceback.print_exc()
            logging.error("Error while killing subprocess - %s" % str(e))

        logging.info("Closed SpyServer Client.")

if __name__ == "__main__":

    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.DEBUG)

    demod = USBDemod(
        ss_iq_path="./ss_iq",
        hostname="kiwisdr.areg.org.au",
        port=5020)

    n = 0
    try:
        while n < 500:
            data = demod.read(1024)
            print(f"Got {len(data)} bytes")
            n += 1

        demod.close()
    except:
        demod.close()