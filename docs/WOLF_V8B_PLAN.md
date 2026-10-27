# Wolf Factory V8B plan

Goal: add a 12-second inactivity timer on top of the hardware-passed V8A INPUT_OBSERVE runtime.

First hardware gate only:
- any observed controller activity resets idle time
- 12 seconds of inactivity publishes a harmless idle-fired marker
- no Wolf Factory launch yet
- no input consumption
- no filter queueing
- V8A safety invariants remain unchanged

A later V8B step may connect the proven trigger to Wolf Factory startup after the timer itself passes on hardware.
