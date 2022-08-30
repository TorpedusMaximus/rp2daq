#!/usr/bin/python3  
#-*- coding: utf-8 -*-
"""
rp2daq.py  (c) Filip Dominec 2020-2022, MIT licensed

This module uses c_code_parser.py to auto-generate the binary message interface. 
Then it connects to Raspberry Pi Pico to control various hardware. 

The methods provided here aim to make the hardware control as convenient as possible.  

More information and examples on https://github.com/FilipDominec/rp2daq or in README.md
"""


MIN_FW_VER = 210400

from collections import deque
import logging
import os
import queue
import serial
from serial.tools import list_ports 
import struct
import sys
import threading
import time
import traceback
import tkinter
import types

import c_code_parser



def init_error_msgbox():  # error handling with a graphical message box
    def myerr(exc_type, exc_value, tb): 
        message = '\r'.join(traceback.format_exception(exc_type, exc_value, tb))
        logging.error(message)
        from tkinter import messagebox
        messagebox.showerror(title=exc_value, message=message)
    sys.excepthook = myerr


class Rp2daq(threading.Thread):
    def __init__(self, required_device_id=None, verbose=False):

        logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, 
                format='%(asctime)s (%(threadName)-9s) %(message)s',) # filename='rp2.log',

        self._register_commands()

        time.sleep(.05)
        self.port = self._find_device(required_device_id=None, required_firmware_version=MIN_FW_VER)

        ## Asynchronous communication using threads
        self.sleep_tune = 0.001
        # TODO Does this have to inherit from Thread? It brings a bunch of unused methods...
        threading.Thread.__init__(self) 
        self.data_receiving_thread = threading.Thread(target=self._data_receiver, daemon=True)
        self.report_processing_thread = threading.Thread(target=self._report_processor, daemon=True)
        self.callback_dispatching_thread = threading.Thread(target=self._callback_dispatcher, daemon=True)

        self.rx_bytes = deque()
        self.run_event = threading.Event()
        self.data_receiving_thread.start()
        self.report_processing_thread.start()
        self.callback_dispatching_thread.start()
        self.run_event.set()

    def _register_commands(self):
        # TODO 0: search C code for version, check it matches that one returned by Raspberry Pi at runtime
        # #define FIRMWARE_VERSION {"rp2daq_220720_"}
        # self.expected_firmware_v = 

        names_codes, markdown_docs  = c_code_parser.generate_command_binary_interface()
        for cmd_name, cmd_code in names_codes.items():
            exec(cmd_code)
            setattr(self, cmd_name, types.MethodType(locals()[cmd_name], self))

        # Search C code for report structs & generate automatically:
        self.sync_report_cb_queues = {}
        self.async_report_cb_queue = queue.Queue()
        self.report_header_lenghts, self.report_header_formats, self.report_header_varnames = \
                c_code_parser.generate_report_binary_interface()

        # Register callbacks (to dispatch reports as they arrive)
        self.report_callbacks = {} 

    def quit(self):
        self.run_event.clear()


    def _data_receiver(self):
        self.run_event.wait()

        while self.run_event.is_set():
                if w := self.port.inWaiting():
                    c = self.port.read(w)
                    #print("  rx", len(c))
                    #print("    ", list( c[:10]), "...", list( c[-10:]))
                    self.rx_bytes.extend(c)
                else:
                    time.sleep(self.sleep_tune)

    def _report_processor(self):
        """
        Thread to continuously check for incoming data.
        When a byte comes in, place it onto the deque.
        """
        def rx_at_least_bytes(length):
            while len(self.rx_bytes) < length:
                #c = self.port.read(w)
                #self.rx_bytes.extend(c) # superfluous bytes are kept in deque for later use
                time.sleep(self.sleep_tune)
            return [self.rx_bytes.popleft() for _ in range(length)]

        self.run_event.wait()

        while self.run_event.is_set():
            try:
                if len(self.rx_bytes):
                    # report_header_bytes will be populated with the received data for the report
                    report_type = self.rx_bytes.popleft()
                    packet_length = self.report_header_lenghts[report_type] - 1

                    report_header_bytes = rx_at_least_bytes(packet_length)

                    #logging.debug(f"received packet header {report_type=} {report_header_bytes=} {bytes(report_header_bytes)=}")

                    report_args = struct.unpack(self.report_header_formats[report_type], 
                            bytes([report_type]+report_header_bytes))
                    cb_kwargs = dict(zip(self.report_header_varnames[report_type], report_args))

                    data_bytes = []
                    if (dc := cb_kwargs.get("_data_count",0)) and (dbw := cb_kwargs.get("_data_bitwidth",0)):
                        payload_length = -((-dc*dbw)//8)  # integer division is like floor(); this makes it ceil()
                        #print("  PL", payload_length)

                        data_bytes = rx_at_least_bytes(payload_length)

                        if dbw == 8:
                            cb_kwargs["data"] = data_bytes
                        elif dbw == 12:      # decompress 3B  into pairs of 12b values & flatten
                            odd = [a + ((b&0xF0)<<4)  for a,b
                                    in zip(data_bytes[::3], data_bytes[1::3])]
                            even = [(c&0xF0)//16+(b&0x0F)*16+(c&0x0F)*256  for b,c
                                    in zip(                   data_bytes[1:-1:3], data_bytes[2::3])]
                            cb_kwargs["data"] = [x for l in zip(odd,even) for x in l]
                            if len(odd)>len(even): cb_kwargs["data"].append(odd[-1])

                        elif dbw == 16:      # using little endian byte order everywhere
                            cb_kwargs["data"] = [a+(b<<8) for a,b in zip(data_bytes[:-1:2], data_bytes[1::2])]

                        #if max(cb_kwargs["data"]) > 2250: print(data_bytes) # XXX
                    

                    cb = self.report_callbacks.get(report_type, False) # false for unexpected reports
                    if cb:
                        #logging.debug("CALLING CB {cb_kwargs}")
                        #print(f"CALLING CB {cb} {cb_kwargs}")
                        ## TODO: enqueue to be called by yet another thread (so that sync cmds work within callbacks,too)
                        ## TODO: check if sync cmd works correctly after async cmd (of the same type)
                        #cb(**cb_kwargs)
                        self.async_report_cb_queue.put((cb, cb_kwargs))
                    elif cb is None: # expected report from blocking command
                        #print(f"UNBLOCKING CB {report_type=} {cb_kwargs}")
                        self.sync_report_cb_queues[report_type].put(cb_kwargs) # unblock default callback (& send it data)
                    elif cb is False: # unexpected report, from command that was not yet called in this script instance
                        #print(f"Warning: Got callback that was not asked for\n\tDebug info: {cb_kwargs}")
                        pass 
                else:
                    time.sleep(self.sleep_tune)

            except OSError:
                logging.error("Device disconnected")
                self.quit()

    def _callback_dispatcher(self):
        """
        """
        self.run_event.wait()

        while self.run_event.is_set():
            (cb, cb_kwargs) = self.async_report_cb_queue.get()
            cb(**cb_kwargs)

    def default_blocking_callback(self, command_code): # 
        """
        Any command called without explicit `_callback` argument is blocking - i.e. the thread
        that called the command waits here until a corresponding report arrives. This is good 
        practice only if quick response from device is expected, or your script uses 
        multithreading. Otherwise your program flow would be stalled for a while here.

        This function is called from *autogenerated* code for each command, iff no _callback
        is specified.
        """
        #print("DBC WAITING", command_code)
        kwargs = self.sync_report_cb_queues[command_code].get() # waits until default callback unblocked
        return kwargs

    def _find_device(self, required_device_id, required_firmware_version):
        """
        Seeks for a compatible rp2daq device on USB, checking for its firmware version and, if 
        specified, for its particular unique vendor name.
        """

        VID, PID = 0x2e8a, 0x000a #  TODO use this info to filter out ports 
        port_list = list_ports.comports()

        for port_name in port_list:

            try_port = serial.Serial(port=port_name.device, timeout=0.01)

            try:
                # TODO if one RP2 is up & running independently, connecting this script to another device
                #       disturbs the former device's operation; get unique serial number w/o messaging?
                #       for a in dir(try_port): print(f'\t{a:20} = {getattr(try_port,a)}')
                #       but 'dmesg' prints out also this: "usb 1-2: SerialNumber: E66058388348892D"
                print(try_port.inWaiting() )
                #try_port.flush()
                #time.sleep(.05) # 50ms round-trip time is enough

                # the "identify" command is hard-coded here, as the receiving threads are not ready yet
                try_port.write(struct.pack(r'<BBB', 1, 0, 1)) 
                time.sleep(.15) # 50ms round-trip time is enough
                bytesToRead = try_port.inWaiting() 
                assert bytesToRead == 1+2+1+30
                id_data = try_port.read(bytesToRead)[4:] 
            except:
                id_data = b''

            if not id_data[:6] == b'rp2daq': 
                logging.info(f"\tport open, but device does not identify itself as rp2daq: {id_data}" )
                continue

            version_signature = id_data[7:13]
            if not version_signature.isdigit() or int(version_signature) < required_firmware_version:
                logging.warning(f"rp2daq device firmware has version {version_signature.decode('utf-8')},\n" +\
                        f"older than this script's {MIN_FW_VER}.\nPlease upgrade firmware " +\
                        "or override this error using 'required_firmware_version=0'.")
                continue

            if isinstance(required_device_id, str): # optional conversion
                required_device_id = required_device_id.replace(":", "")
            found_device_id = id_data[14:]
            if required_device_id and found_device_id != required_device_id:
                logging.info(f"found an rp2daq device, but its ID {found_device_id} does not match " + 
                        f"required {required_device_id}")
                continue

            logging.info(f"connected to rp2daq device with manufacturer ID = {found_device_id.decode()}")
            return try_port
        else:
            msg = "Error: could not find any matching rp2daq device"
            logging.critical(msg)
            raise RuntimeError(msg)



if __name__ == "__main__":
    print("Note: Running this module as a standalone script will only try to connect to a RP2 device.")
    print("\tSee the 'examples' directory for further uses.")
    rp = Rp2daq()       # tip: you can use required_device_id='42:42:42:42:42:42:42:42'
    t0 = time.time()

    #rp.pin_set(11, 1, high_z=1, pull_up=1)
    #print(rp.pin_get(11))
    #rp.pwm_configure_pair(0, clkdiv=255, wrap_value=500)
    #rp.pwm_set_value(0, 200)
    #rp.pwm_configure_pair(0, clkdiv=255, wrap_value=500)
    #rp.pwm_set_value(1, 100)
    #rp.pwm_configure_pair(2, clkdiv=255, wrap_value=1000)
    #rp.pwm_set_value(2, 300)



