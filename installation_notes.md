# Installation notes

If you are using a Point Grey/FLIR camera, make sure the [FlyCapture SDK](https://www.flir.com/products/flycapture-sdk/) is installed. Copy FlyCapture2_C.dll from the Point Grey directory (it is in the bin folder - for instance, C:\Program Files\Point Grey Research\FlyCapture2\bin64) and place it in your FicTrac directory. If it is named FlyCapture2_C_v100.dll rename it.

For closed loop, or general purpose tracking, FicTrac needs to be installed. In order to do this, first download the pre-built binaries available [here](https://github.com/murthylab/fictrac/releases/tag/v2.0.2).

For configuring FicTrac, a few files are needed:
1. A TIFF file used as a mask to remove non-ball areas, bright spots, etc (show examples). There is currently a matlab function that will help create this mask available in Im2P_CreateNewMask.m. But first need to capture a single frame to use as reference point!

Note that you probably want to reduce the resolution of the frame to minimize how much data needs to be passed around.

2. A configuration file. Currently in FicTracPGR_ConfigMaster.txt

3. A calibration file (??). Currently in calibration-transform.dat. If you do not use this transform file, a new one will be created by a user-guided process the first time you run FicTrac. If you want to update it, you can delete the file and try again.

4. To run FicTrac, run FicTrac FicTracPGR_ConfigMaster.txt or FicTrac-PGR FicTracPGR_ConfigMaster.txt (if you are using a Point Grey camera).