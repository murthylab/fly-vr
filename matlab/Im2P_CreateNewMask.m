%Im2P_CreateFilesForFicTrac checks if the last mask is correct, and if not - asks the
%user to create a new mask. 

%Note: if CheckMask=0, the last modified *MASK* file in Calibration_Directory will be
%used, so do CheckMask=0 only if you are SURE that this mask is good.
%Any doubt? Do CheckMask = 1

function Im2P_CreateNewMask(Calibration_Directory)

% Calibration_Directory = 'D:\flyVR\Calibration_folder';%upstate 2P
% Calibration_Directory = 'E:\FicTracWin64\Calibration_folder';%downstairs 2P


addpath(genpath('Z:\Dudi\MatlabProg\'))
cleanpath, savepath


%FicTrac main folder path
CurrDir = cd(Calibration_Directory);
%Upload the last mask and snap files

%find the most updated MASK file
MASKfiles = dir('*mask*');
DateModified = zeros(1,size(MASKfiles,1));
for nMaskFile = 1:size(MASKfiles,1)
   DateModified(nMaskFile) = datenum(MASKfiles(nMaskFile).date);
end
MaskFile = fullfile(pwd,MASKfiles(DateModified == max(DateModified)).name);
MASK_filename = MaskFile;%use the last mask modified in Calibration_Directory (default, if not changed later)
MASK = imread(MaskFile);
if size(MASK,3) == 3%if the image file is a true RGB image file, convert
   MASK = rgb2gray(MASK);
end

%find the most updated SNAP file
SNAPfiles = dir('*snap*');
DateModified = zeros(1,size(SNAPfiles,1));
for nSnapFile = 1:size(SNAPfiles,1)
   DateModified(nSnapFile) = datenum(SNAPfiles(nSnapFile).date);
end

SnapFile = fullfile(pwd,SNAPfiles(DateModified == max(DateModified)).name);
if size(imread(SnapFile),3)>1
   SNAP = rgb2gray(imread(SnapFile));
else
   SNAP = imread(SnapFile);
end

width = size(SNAP,2);
height = size(SNAP,1);

%show snap with transparent mask overlaid
figure(1); clf
colormap(gray)
C = imfuse(SNAP,MASK,'blend');
imshow(C)

%Updated mask by user if needed
prompt = 'Mask OK? Y/N [Y]: ';
while 1
   IsOK = input(prompt,'s');
   if isempty(IsOK)
      IsOK = 'Y';%default
   end
   if strcmpi(IsOK,'N') || strcmpi(IsOK,'Y'), break, end
   disp('Wrong input value, Y/N only')
end


%create new mask
if strcmpi(IsOK,'N')
   MaskOK = 0;
   imageSizeX = size(SNAP,2);
   imageSizeY = size(SNAP,1);
   [columnsInImage, rowsInImage] = meshgrid(1:imageSizeX, 1:imageSizeY);
   while 1
      %user defines ball circle
      disp('Define ball borders')
      fig = figure(1); clf(fig)
      imshow(SNAP)
      [x, y] = getpts(fig);
      [xc,yc,R,~] = circfit(x,y);
      config_shpere_centre_px = ['sphere_centre_px    ',num2str(round(xc,2)),' ',num2str(round(yc,2))];
      

      config_sphere_radius_px = ['sphere_radius_px    ',num2str(round(R,2))];
      disp(config_shpere_centre_px)
      disp(config_sphere_radius_px)
      BallPixels = (rowsInImage - yc).^2 ...
         + (columnsInImage - xc).^2 <= R.^2;
      BallMASK = BallPixels;% circlePixels is white - mask on
      
      %
      sphere_cx_px=round(xc,2);
      sphere_cy_px=round(yc,2);
      sphere_radius_px=round(R,2);
      %
      
      %
      
      %user defines glare circle
      disp('Define glare borders')
      fig = figure(1); clf(fig)
      imshow(SNAP)
      [x, y] = getpts(fig);
      [xc,yc,R,~] = circfit(x,y);
      
      glarePixels = (rowsInImage - yc).^2 ...
         + (columnsInImage - xc).^2 <= R.^2; % circlePixels is a 2D "logical" array.
      GlareMASK = 1 - glarePixels;%so that the glare is black - mask off
      
      %user defines ball holder
      while 1
         disp('Define holder upper point (1 point)')
         fig = figure(1); clf(fig)
         imshow(SNAP)
         [x, y] = getpts(fig);
         if length(x) == 1
            break
         else
            disp('1 point only please..')
         end
      end
      
      
      
      %create a black mask for the part of the holder that shadows the ball
      %(1) straight line under the ball (in any image orientation)
      %(2) black all the way to the bottom (just in case the bottom was marked wrongly)
      %Assuming: air stream axis: up
      xx = [1 size(SNAP,2) size(SNAP,2) 1];
      yy = [size(SNAP,1) size(SNAP,1) y y];
      
      BallHolder = poly2mask(xx, yy, size(SNAP,1), size(SNAP,2));
      BallHolderMASK = 1 - BallHolder; %so that the ball holder is black - mask off
      
      %make mask
      MASK = BallMASK & GlareMASK & BallHolderMASK;
      
      fig = figure(1); clf(fig)
      C = imfuse(SNAP,MASK,'blend');
      imshow(C)
      
      prompt = 'Mask OK? Y/N [Y]: ';
      while 1
         IsOK = input(prompt,'s');
         if isempty(IsOK)
            IsOK = 'Y';
         end
         if strcmpi(IsOK,'N') || strcmpi(IsOK,'Y'), break, end
         disp('Wrong input value, Y/N only')
      end
      
      if strcmpi(IsOK,'y'), MaskOK = 1; end
      
      if MaskOK == 1
         %DATE = char(datetime('now','Format','yyMMdd'));
         MASK_filename = fullfile(Calibration_Directory,'MASK.tiff');%will be updated and used for FicTrac online tracking
         delete(MASK_filename)
         imwrite(MASK,MASK_filename)
         break
      end
   end
   
   %delete old SNAP and MASK files
   %find the most updated MASK file
   MASKfiles = dir('*mask*');
   for nMaskFile = 1:size(MASKfiles,1)
      filename = MASKfiles(nMaskFile).name;
      if ~contains(MASK_filename,filename)
         delete(filename)
      end
   end
   
   
   %find the most updated SNAP file
   SNAPfiles = dir('*snap*');
   for nSnapFile = 1:size(SNAPfiles,1)
      filename = SNAPfiles(nSnapFile).name;
      if ~contains(SnapFile,filename)
         delete(filename)
      end
   end
   
   
else
   disp('Mask wasnt modified')
   
end

%update the file calibration-transform in the calibration folder
if exist(fullfile(Calibration_Directory,'calibration-transform.dat'),'file')
   delete(fullfile(Calibration_Directory,'calibration-transform.dat'))
end

Im2P_VR_FicTracCalibrationCalc(sphere_cx_px,sphere_cy_px,sphere_radius_px,...
    width, height, Calibration_Directory)

cd(CurrDir)

end

