#!/usr/bin/python3  
#-*- coding: utf-8 -*-

NANOSTEP_PER_MICROSTEP = 256
MINIMUM_POS = -2**22

CMD_IDENTIFY = 123
CMD_MOVE_SYMBOL = 1
CMD_GET_STEPPER_STATUS =  3
CMD_INIT_STEPPER = 5 
CMD_SET_PWM = 20
CMD_INIT_PWM = 21 
# TODO SYMBOLS HERE

CMD_APPROACH =  2
CMD_GET_STM_STATUS =  4
CMD_SET_PIEZO =  9
CMD_LINESCAN = 10

import sys
import time
import tkinter
import os
import serial
import struct


def init_error_msgbox():  # error handling with a graphical message box
    import traceback, sys
    def myerr(exc_type, exc_value, tb): 
        message = '\r'.join(traceback.format_exception(exc_type, exc_value, tb))
        print(message)
        from tkinter import messagebox
        messagebox.showerror(title=exc_value, message=message)
    sys.excepthook = myerr

def init_settings(infile='settings.txt'):
    #infile = os.path.realpath(__file__)
    #print("DEBUG: infile = ", infile)
    settings = {}
    with open(infile) as f:
        for l in f.readlines():
            l = l.split('#')[0] # ignore comments
            k,v = [s.strip() for s in l.split('=', 1)]  # split at first '=' sign
            settings[k] = v
    return settings

class Rp2daq():
    def __init__(self, serial_port_names=None, required_device_tag=None):
        if not serial_port_names:
            if os.name=='posix':    # e.g. for Linux
                #serial_port_names = '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2'
                serial_port_names = '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2'
            else:   # for Windows
                serial_port_names = 'COM0', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5'   

        for serial_port_name in serial_port_names:
            try:
                if os.name == 'posix':
                    import termios
                    with open(serial_port_name) as f: # 
                        attrs = termios.tcgetattr(f)
                        ## On Linux one needs first to disable the "hangup" signal, to prevent rp232 randomly resetting. 
                        ## A command-line solution is: stty -F /dev/ttyUSB0 -hup
                        attrs[2] = attrs[2] & ~termios.HUPCL
                        termios.tcsetattr(f, termios.TCSAFLUSH, attrs)

                # Standard serial port settings, as hard-coded in the hardware
                self.port = serial.Serial(port=serial_port_name, baudrate=baudrate, bytesize=serial.EIGHTBITS, 
                        parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout= 0.1) # default is "8N1"

                # TODO port.write(struct.pack(r'<B', CMD_IDENTIFY)
                # time.sleep(.1): port.read(30)
                # TODO if not [:6] == 'rp2daq': # needed: implement timeout!
                #       print(f"{serial_port_name} exists, but is not the right device); continue
                # if select_device_tag=None
                return
            except IOError:
                pass        # termios is not available on Windows, but probably also not needed
        raise RuntimeError("Could not connect to the rp232 device" + 
                (f"with tag"+required_device_tag if required_device_tag else ""))


    #def init_stepper(self, assign_id, assign_step_pin, assign_dir_pin, assign_endstop_pin=None, motor_inertia=256):
        #raise NotImplementedError

    def identify(self):
        self.port.write(struct.pack(r'<B', CMD_IDENTIFY))
        raw = self.port.read(30)
        return raw

    def init_stepper(self, motor_id, dir_pin, step_pin, endswitch_pin, disable_pin, motor_inertia=128):
        self.port.write(struct.pack(r'<BBBBBBi', CMD_INIT_STEPPER, motor_id, dir_pin, step_pin, endswitch_pin, disable_pin, motor_inertia))

    def get_stepper_status(self, motor_id):       
        """ Universal low-level stepper motor control: returns a dict indicating whether the motor is running, 
        another whether it is on end switch and an integer of the motor's current nanoposition. """
        self.port.write(struct.pack(r'<BB', CMD_GET_STEPPER_STATUS, motor_id))
        raw = self.port.read(6)
        print('STEPPER RAW', raw)
        vals = struct.unpack(r'<BBi', raw)
        print('    --> STEPPER STATUS', vals)
        try:
            return dict(zip(['active', 'endswitch', 'nanopos'], vals))
        except:
            return dict(zip(['active', 'endswitch', 'nanopos'], [0,0,0]))

    def stepper_move(self, motor_id, target_micropos, nanospeed=256, endstop_override=False, wait=False): 
        """ Universal low-level stepper motor control: sets the new target position of the selected
        stepper motor, along with the maximum speed to be used. """
        # FIXME in firmware: nanospeed should allow (a bit) more than 256
        if target_micropos < MINIMUM_POS: 
            target_micropos = MINIMUM_POS
        self.port.write(struct.pack(r'<BBiiB', CMD_MOVE_SYMBOL, motor_id, 
                target_micropos*NANOSTEP_PER_MICROSTEP, nanospeed, 
                1 if endstop_override else 0))
        print(motor_id, target_micropos*NANOSTEP_PER_MICROSTEP)
        if wait:
            while self.get_stepper_status(motor_id=motor_id)['active']: 
                time.sleep(.1)   
    
    def init_pwm(self, assign_channel=1, assign_pin=19, bit_resolution=16, freq_Hz=100, init_value=6654):
        self.port.write(struct.pack(r'<BBBBii', 
            CMD_INIT_PWM, 
            assign_channel, 
            assign_pin, 
            bit_resolution,
            freq_Hz,
            init_value))

    def set_pwm(self, val, channel=1):
        self.port.write(struct.pack(r'<BBi', 
            CMD_SET_PWM, 
            channel, 
            int(val)))


    def get_stm_status(self):
        self.port.write(struct.pack(r'<B', CMD_GET_STM_STATUS))
        raw = []
        for count in range(100):
            time.sleep(.10)
            raw = self.port.read(2000*2)
            if len(raw)==4000: break
            print('waiting extra time for serial data...')
            self.port.write(struct.pack(r'<B', CMD_GET_STM_STATUS))

        status = dict(zip(['tip_voltage'], [struct.unpack(r'<2000H', raw)]))
        #status['stm_data'] = struct.unpack(r'<{:d}h'.format(status['stm_data_len']//2), self.port.read(status['stm_data_len']))
        return status


# https://www.aranacorp.com/en/using-the-eeprom-with-the-rp232/
