%Im2P_CreateFilesFor_flyvr creates a new folder for flyVR, including all
%the neccesary files for running flyVR

%missing: update stimulus name in the flyvr config file
%also - the output name should include the date/session so that it will be unique!


addpath(genpath('Z:\Dudi\MatlabProg\'))
cleanpath, savepath

%Parameters
Calibration_Directory = 'E:\FicTracWin64\Calibration_folder';
% Experiment_Directory = 'E:\Data\Max'; % change for each fly
Experiment_Directory = 'E:\Data\flyvr-nivama'; % change for each fly
% StimFile = 'E:\flyvr-tests\OptoFiles\Max_aud_olf.txt';
% StimFile = 'E:\flyvr-tests\OptoFiles\opto_nivamasan_10sON90sOFF.txt';

StimFile = 'E:\flyvr-tests\OptoFiles\opto_mdn_2.txt';

%flags
IsClosedLoop = 0;%open or closed loop experiments
IsShuffle = 0;%shuffle the order of the auditory stim. Relevant only in open loop experiments, otherwise ignored

%new folders to prepare
Sessions = 101:105; % can make multiple sessions, e.g., 101:110
IsOverride = 1;

%% check that all files are ready

%FicTrac files
FicTracConfig_file = fullfile(Calibration_Directory,'FicTracPGR_ConfigMaster.txt');
if exist(FicTracConfig_file,'file') == 0
   disp(['Missing FicTracConfig file: ',FicTracConfig_file,' doesnt exist'])
   return
end

Mask_file = fullfile(Calibration_Directory,'MASK.tiff');
if exist(Mask_file,'file') == 0
   disp(['Missing MASK file: ',Mask_file,' doesnt exist'])
   return
end

CalibrationTransform_File = fullfile(Calibration_Directory,'calibration-transform.dat');
if exist(CalibrationTransform_File,'file') == 0
   disp(['Missing calibration-transform file: ',CalibrationTransform_File,' doesnt exist'])
   return
end


if IsClosedLoop == 0
   if exist(StimFile,'file') == 0
      disp(['Missing Stim file: ',StimFile,' doesnt exist'])
      return
   end
   FlyvrConfig_file = fullfile(Calibration_Directory,'FlyvrConfigMaster_openloop.txt');
   if exist(FlyvrConfig_file,'file') == 0
      disp(['Missing FlyVR openloop config file: ',FlyvrConfig_file,' doesnt exist'])
      return
   end
elseif IsClosedLoop == 1
   FlyvrConfig_file = fullfile(Calibration_Directory,'FlyvrConfigMaster_closedloop.txt');
   if exist(FlyvrConfig_file,'file') == 0
      disp(['Missing FlyVR closedloop config file: ',FlyvrConfig_file,' doesnt exist'])
      return
   end
   
end

%Ask user if the calibration file is updated for the new mask  (based on
%dates)
MaskFile = dir(Mask_file);
CalibFile = dir(CalibrationTransform_File);

disp(['Mask file modified on: ',MaskFile.date])
disp(['Calibration file modified on: ',CalibFile.date])
prompt = 'Calibration file OK? Y/N [Y]: ';
while 1
   IsOK = input(prompt,'s');
   if isempty(IsOK)
      IsOK = 'Y';
   end
   if strcmpi(IsOK,'N') || strcmpi(IsOK,'Y'), break, end
   disp('Wrong input value, Y/N only')
end

if strcmpi(IsOK,'N')
   disp('Please update calibration file')
   return
end

disp('All files are ready, creating new folders with all relevant files for flyVR')


%%
DateString = datestr(datetime('now'),'yymmdd');
for nSession = 1:length(Sessions)
   NewFolder = fullfile(Experiment_Directory,[DateString,'_',num2str(Sessions(nSession))]);
   
   %check if the new folder already exist
   if exist(NewFolder,'file') && IsOverride == 1
      prompt = ['Override ',NewFolder,' ?'];
      while 1
         IsOK = input(prompt,'s');%ask the user just to be on the safe side
         if isempty(IsOK)
            IsOK = 'Y';
         end
         if strcmpi(IsOK,'N') || strcmpi(IsOK,'Y'), break, end
         disp('Wrong input value, Y/N only')
      end
      if strcmpi(IsOK,'N'), return,end %don't override
      %empty the folder
      filePattern = fullfile(NewFolder, '*'); % all files in the folder
      theFiles = dir(filePattern);
      for k = 1 : length(theFiles)
         baseFileName = theFiles(k).name;
         fullFileName = fullfile(NewFolder, baseFileName);
         fprintf(1, 'Now deleting %s\n', fullFileName);
         delete(fullFileName);
      end
      
      disp(['Overriding folder "',NewFolder,'"'])
   elseif exist(NewFolder,'file') && IsOverride == 0
      disp(['Folder "',NewFolder,'" already exist, returning.'])
   end
   
   mkdir(NewFolder)
   disp(['Folder ',NewFolder,' was created'])
   copyfile(Mask_file,fullfile(NewFolder,'MASK.tiff'))
   copyfile(CalibrationTransform_File,fullfile(NewFolder,'calibration-transform.dat'))
   copyfile(FicTracConfig_file,fullfile(NewFolder,'FicTracPGR_Config.txt'))
   copyfile(FlyvrConfig_file,fullfile(NewFolder,'FlyvrConfig.txt'))
   disp('Files copied to new folder')
   
   
   output_filename = [DateString,'_',num2str(Sessions(nSession)),'_output.h5'];
   
   
   %update FlyvrConfig.txt
   fid = fopen(FlyvrConfig_file);
   if fid == -1, disp('wrong config file name'),return,end
   new_fid = fopen(fullfile(NewFolder,'FlyvrConfig.txt'),'wt');
   
   if IsClosedLoop == 0
      while 1
         tline = fgets(fid);
         disp(tline)
         if ~isempty(strfind(tline,'stim_playlist'))
            newline = ['stim_playlist=          ',StimFile];
            fprintf(new_fid, '%s\n',newline);
         elseif IsShuffle == 1 && ~isempty(strfind(tline,'shuffle'))
            newline = 'shuffle=								True';%default = False
            fprintf(new_fid, '%s\n',newline);
         elseif ~isempty(strfind(tline,'record_file'))
            newline = ['record_file=            ',output_filename];
            fprintf(new_fid, '%s\n',newline);
         elseif ~isempty(strfind(tline,'fictrac_config'))
            newline = ['fictrac_config=            ','FicTracPGR_Config.txt'];
            fprintf(new_fid, '%s\n',newline);
         elseif ~isempty(strfind(tline,'pgr_cam_enable'))
            fprintf(new_fid, '%s\n',tline);
            break
         else
            fprintf(new_fid, '%s\n',tline);
         end
      end
      
   elseif IsClosedLoop == 1
      while 1
         tline = fgets(fid);
         disp(tline)
         if ~isempty(strfind(tline,'record_file'))
            newline = ['record_file=            ',output_filename];
            fprintf(new_fid, '%s\n',newline);
         elseif ~isempty(strfind(tline,'fictrac_config'))
            newline = ['fictrac_config=            ','FicTracPGR_Config.txt'];
            fprintf(new_fid, '%s\n',newline);
         elseif ~isempty(strfind(tline,'pgr_cam_enable'))
            fprintf(new_fid, '%s\n',tline);
            break
         else
            fprintf(new_fid, '%s',tline);
         end
      end
      
   end
   
end

fclose(fid);
fclose(new_fid);

