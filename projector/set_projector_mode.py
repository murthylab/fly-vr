from dlplc_tcp import *

import ProjectorStimuli

print ("Setting projector display mode to HDMI")
dlplc = LightCrafterTCP()
if not dlplc.connect():
    print("Unable to connect to device.")
    sys.exit(1)

dlplc.cmd_current_display_mode(0x02)
dlplc.cmd_current_video_mode(frame_rate=60, bit_depth=7, led_color=4)