# Installation notes

For closed loop, or general purpose tracking, FicTrac needs to be installed. In order to do this, first download the pre-built binaries available [here](https://github.com/murthylab/fictrac/releases/tag/v2.0.2).

For configuring FicTrac, a few files are needed:
1. A TIFF file used as a mask to remove non-ball areas, bright spots, etc (show examples). There is currently a matlab function that will help create this mask available in Im2P_CreateNewMask.m. But first need to capture a single frame to use as reference point!

Note that you probably want to reduce the resolution of the frame to minimize how much data needs to be passed around.

2. A configuration file. Currently in FicTracPGR_ConfigMaster.txt
3. A calibration file (??). Currently in calibration-transform.dat