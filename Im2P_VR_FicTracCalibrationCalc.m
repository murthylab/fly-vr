%This function creates a new calibration_transform file, based
%on the position of the ball in the image (center, radius). These values
%are calculated by either Im2P_CreateNewMask or Im2P_VR_Update_mask who are
%both calling this function

%VFOV:
%The vfov could be calculated by trigenometry (move the ball away from camera, measure 
%Y a few times and find the angle vfov in degrees),and couldf be optimized by rotating a
%stepper moter and finding the vfov that makes no jump at the end of each 360deg ball rotation.
%Note that the vfov for a given setup (a given camera location and camera zoom)also depends of the image size
%So if for example vfov = 2.15 for 480 vertical pixels, for 640 vertical pixels do vfov = 640/480*2.15 pixels)

%with point grey Flee3 FL3-U3-13Y3M and the objective: https://computar.com/product/559/MLM3X-MP,
%with the mamera at the largest possible distance from the ball, max zoom
%and 480*480 pixels, the VFOV is 2.15deg.
%So with 960*960 (fits better a 9mm ball)is should be around 4.5deg

function Im2P_VR_FicTracCalibrationCalc(sphere_cx_px,sphere_cy_px,sphere_radius_px,...
    width,height,Calibration_Directory)

%Parameters
ConfigFile = fullfile(Calibration_Directory,'FicTracPGR_ConfigMaster.txt');
SaveTo = fullfile(Calibration_Directory,'calibration-transform.dat');

%Find the VFOV in the ConfigMaster file
fileID = fopen(ConfigFile,'r');
TEXT = fscanf(fileID,'%s');
START = strfind(TEXT,'vfov')+4;
temp = strfind(TEXT(START:end),'%');
END = START + temp(1) - 2;
vfov = str2double(TEXT(START:END));


% example: lines 1-3 with z down (during an experiment). Need to round.
line1 = '-1 0 0';
line2 = '0 0 1';
line3 = '0 1 0';

%line 4 is unused, so leave as
line4 = '0 0 0';

%line 5 (after normalization). It's a vector (3 coordinates) -
PixToVec = @(x,y) [(x+.5) - width*.5, (y+.5) - height*.5 , height * 0.5 / tan(vfov * 0.5)];
sphere_centre = PixToVec(sphere_cx_px, sphere_cy_px);
sphere_centre = sphere_centre / norm(sphere_centre);
line5 = num2str(sphere_centre);


%line 6 -
sphere_circum = PixToVec(sphere_cx_px + sphere_radius_px, sphere_cy_px);
sphere_circum = sphere_circum / norm(sphere_circum);
sphere_fov = acos(dot(sphere_centre, sphere_circum))*2;%!!!! I added the deg2rad here (Dudi, 7/17, 9:53pm)
line6 = num2str(sphere_fov);


%lines 7-8 (for black and white ball) -
line7 = '0 0 0';
line8 = '0 0 0';

%line 9 - vfov
line9 = num2str(vfov,6);

%line 10
line10 = '0';


%write to file
fid = fopen(SaveTo,'wt');

if fid == -1, disp('wrong FicTracConfig file name'),return,end
fprintf(fid, '%s\n',line1);
fprintf(fid, '%s\n',line2);
fprintf(fid, '%s\n',line3);
fprintf(fid, '%s\n',line4);
fprintf(fid, '%s\n',line5);
fprintf(fid, '%s\n',line6);
fprintf(fid, '%s\n',line7);
fprintf(fid, '%s\n',line8);
fprintf(fid, '%s\n',line9);
fprintf(fid, '%s\n',line10);

fclose(fid);
 
end

