# RP2DAQ - Raspberry Pi Pico for Data Acquisition (and much more)

Raspberry Pi Pico is a small, but quite powerful microcontroller board. When connected to a computer over USB, it can serve as an interface to hardware - which may be as simple as a digital thermometer, or as complicated as scientific experiments tend to be. 

This project presents both precompiled firmware and a user-friendly Python module to control it. The firmware takes care of all technicalities at the microcontroller side including parallel task handling and reliable communication, and is optimized to harness Raspberry Pi's maximum performance. All actions of RP2DAQ are triggered by the Python script in the computer. This saves the user from programming in C and from error-prone hardware debugging. Even without any programming, one can try out few supplied *Example programs*. 

If needed, entirely new capabilities can be added into the [open source](LICENSE) firmware. More is covered in the [developer documentation for the C firmware](DEVELOPERS.md). Contributing new code back is welcome. 


## Status: Work under progress

**Work under progress. Not ready enough to be recommended for practical use yet.**

 * Basic features: 
    * [x] async message communication
    * [ ] fresh rewritten stepper control
    * [ ] analog pin direct read
	* [ ] digital pin input/output
 * Documentation:
    * [ ] No programming: setting up hardware and first tests
    * [ ] Python programming: basic concepts and examples
    * [ ] C programming: extending rp2daq's capabilities
    * [ ] Presumably asked questions
 * Advanced features
    * [x] second core for time-critical tasks
    * [x] o/c @250 MHz

## Getting it work

#### What will you need

 * Raspberry Pi Pico ($5),
 * USB micro cable ($3),
 * a computer with with [Python (3.8+)](https://realpython.com/installing-python/) and ```python-pyserial``` package installed.
	* On Windows, [get anaconda](https://docs.anaconda.com/anaconda/install/windows/) if unsure.
	* On Linux, Python3 should already be there
    * On Mac, it should be there though [version update](https://code2care.org/pages/set-python-as-default-version-macos) may be needed

#### Uploading the firmware to Raspberry (once)

1. [Download](https://github.com/FilipDominec/rp2daq/archive/refs/heads/main.zip) and unzip this project. 
    * (If preferred, one can also use ```git clone https://github.com/FilipDominec/rp2daq.git```)
1. Holding the white "BOOTSEL" button on Raspberry Pi Pico, connect it to your computer with the USB cable. Release the ```BOOTSEL``` switch.
    * In few seconds it should register as a new flash drive, containing INDEX.HTM and INFO_UF2.TXT. 
1. Copy the ```build/rp2daq.uf2``` file to RP2. 
    * *The flashdrive should disconnect immediately.* 
    * *The green diode on RP2 should blink twice, indicating the firmware is running and awaiting commands.*
After few seconds, the USB storage should disconnect. Your RP2 becomes accessible for any program as a new COM/ttyACM port.  Let's try it.

#### Hello world

## Example programs

#### Morse code transmitter

TBA

#### Temperature record

TBA

#### Graphical oscilloscope

TBA


## PAQ - Presumably Asked Questions

**Q: How does RP2DAQ differ from writing MicroPython scripts directly on RP2?**

A: Fundamentally, but use cases may overlap. [MicroPython](https://github.com/micropython/micropython) (and [CircuitPython](https://circuitpython.org/)) interpret Python code directly on a microcontroller (including RP2), so they are are good choice for a stand-alone device (if speed of code execution is not critical, which may be better addressed by custom C firmware). There are many libraries that facilitate development in MicroPython. 

In contrast, RP2DAQ assumes the microcontroller is constantly connected to computer via USB; then the precompiled firmware efficiently handles all actions and communication, so that you only need to write one Python script for your computer. 

**Q: Is the use of RP2DAQ limited to Raspberry Pi Pico board? **

A: Very likely it can be transferred other boards featuring the RP2040 microcontroller, but this is not yet tested. The pin definitions would obviously change. 


**Q: Are there projects with similar scope?**

A: [Telemetrix](https://github.com/MrYsLab/Telemetrix4RpiPico) also uses RP2 as a device controlled from Python script in computer. RP2DAQ aims for higher performance in laboratory automation. However, parts of RP2DAQ code and concepts were inspired by Telemetrix.

**Q: Does RP2DAQ implement all functions available by the Raspberry Pico SDK?**

A: By far not - and it is not even its scope. RP2DAQ's features make a higher layer above (a subset) of the SDK functions.


**Q: Does RP2DAQ help communicating with scientific instruments, e.g. connected over GPIB/VISA?**

A: Interfacing to instruments is outside of RP2DAQ's scope, but [over 40 other projects](https://github.com/python-data-acquisition/meta/issues/14) provide Python interfaces for instrumentation and they can be imported into your scripts independently. While RP2DAQ does not aim to provide such interfaces, capabilities of RP2 could substitute some commercial instruments in less demanding use cases. 


**Q: Why are no displays or user interaction devices supported?**

A: The Python script has much better display and user interaction interface - that is, your computer. RP2DAQ only takes care for the hardware interaction that computer cannot do. 


**Q: Can RP2DAQ control unipolar stepper motors using ULN2003?**

A: No. Both bipolar and unipolar steppers seem to be supported by stepstick/A4988 modules, with better accuracy and efficiency than provided by ULN2003. 


## Legal

The firmware and software are released under the [MIT license](LICENSE). 

They are free as speech after drinking five beers, that is, with no warranty of usefulness or reliability. RP2DAQ cannot be recommended for industrial process control.



