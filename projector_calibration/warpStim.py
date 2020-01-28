
###
# http://paulbourke.net/dome/warpingfisheye/
# to generate warp stim:
# first line: indicates image type ("2" for fisheye - windowwarp demands this)
# second line: two numbers containing the dimensions of the 2D mesh (number nodes horizontally, number nodes vertically)
# each subsequent line: 
# - position of node in normalized screen coordinates [-1,1] x,y, 
# - texture coordinate of the node range from [0,1] to apply to the mesh u,v
# - a multiplicative intensity value [0,1] to correct for light density
###

# note that pyglet>=1.4 doesn't work...!


from psychopy import visual, core, event
from psychopy.visual.windowwarp import Warper

# mywin = visual.Window([1440,900],monitor='testMonitor', 
             # fullscr=True, useFBO = True)

# mywin = visual.Window([1440,900],monitor='testMonitor', screen=1,
#              useFBO = True)

# mywin = visual.Window([1440,900],monitor='testMonitor', screen=1,
#              useFBO = True)

mywin = visual.Window([608,684],monitor='testMonitor', screen=1,
             useFBO = True)

# mywin = visual.Window([1440,900],monitor='testMonitor')

print('finally')
warper = Warper(mywin,
                # warp='spherical',
                warp='warpfile',
                warpfile = "calibratedBallImage.data",
                warpGridsize = 300,
                eyepoint = [0.5, 0.5],
                flipHorizontal = False,
                flipVertical = False)

# warper.dist_cm = 10.0
# warper.changeProjection('spherical')

print('??')

#create some stimuli
fixation = visual.GratingStim(win=mywin, size=5, pos=[0,0], sf=50, color=-1)

# fixation = visual.Rect(
#     win=mywin,
#     width=0.8,
#     height=0.4,
#     fillColor=[1, -1, -1],
#     lineColor=[-1, -1, 1]
# )
fixation.draw()
mywin.update()

#pause, so you get a chance to see it!
# core.wait(5)
event.waitKeys()