function varargout = prvGreyPlayback4(varargin)
% Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
   'gui_Singleton',  gui_Singleton, ...
   'gui_OpeningFcn', @prvGreyPlayback4_OpeningFcn, ...
   'gui_OutputFcn',  @prvGreyPlayback4_OutputFcn, ...
   'gui_LayoutFcn',  [] , ...
   'gui_Callback' ,   []);
if nargin && ischar(varargin{1})
   gui_State.gui_Callback = str2func(varargin{1});
end

if nargout
   [varargout{1:nargout}] = gui_mainfcn(gui_State, varargin{:});
else
   gui_mainfcn(gui_State, varargin{:});
end
% End initialization code - DO NOT EDIT


% --- Executes just before prvGreyPlayback4 is made vsible.
function prvGreyPlayback4_OpeningFcn(hObject, eventdata, handles, varargin)
%% parse config
disp('setting up:')
global p s v

set(handles.startButton,'Enable','off')
set(handles.exitButton,'Enable','off')

% check if OpeningFcn is called from a running instance of prvGreyPlayback4
if isempty(p) || (isfield(p, 'exit') && p.exit==1)
   p.configFileName = varargin{1};
   disp(['  reading config ' p.configFileName])
   % first init - choose default user
   p = feval(p.configFileName,'');
   set(handles.popupmenu4, 'String',p.userList);
   set(handles.popupmenu4,'Value', p.defaultUser);
   p.exit = 0;
end
% get default user
userList = get(handles.popupmenu4,'String');
currentUser = userList{get(handles.popupmenu4,'Value')};
disp(['  loading ' currentUser])

% load parameters for this physical setup - you can define CHANNELS, VIDEO etc in the .m file p.configFileName
% currentUser is an argument - enable setting user specific parameters
p = feval(p.configFileName, currentUser);
%% parse attenuation file
% attenuate with freq spec scaling, so that 1V corresponds to 1 mm/s for
% sine song. For white noise var of 0.007V and noise band 80-1000 Hz yields 1 mm/s
% 0 Hz - white noise, -1 Hz - no attenuation
if ~isempty(p.niChannelOut)
   tb = readtable(p.attenuationSineFile, 'Delimiter', '\t');                  % parse attenuation file, should come in FREQUENCY (Hz) - attenuation factor terms, such that int is 1mm/s
   if strcmpi(tb.Properties.VariableNames{1}, 'x_Freq')                       % fix old format attenuation files
      tb.Properties.VariableNames{1} = 'freq';
   end
   p.attenuation.freqs = tb.freq;                                             % populate ATTENUATION structure with freqs...
   p.attenuation.attenuation = tb{:,2:end};                                   % ...and attenuation factors
   p.attenuation.transferFunction = importdata( p.attenuationConvFile,p.attenuationConvVariable);% load kernel to equalize broad band stimuli
end
%% setup daq
disp('  setting up DAQ.')
daqreset()
boards=daq.getDevices;

% find correct device
hits = find(strcmpi(p.niDevIn, {boards.ID}));
p.sessionType = boards(hits(1)).Vendor.ID;
s=daq.createSession(p.sessionType);

% NI daq - add analog input and output channels
if strcmpi(p.sessionType, 'ni')
   if ~isempty(p.niChannelIn)
      s.addAnalogInputChannel(p.niDevIn,p.niChannelIn,'voltage');
      if any(p.respCh)
         [s.Channels(p.respCh).InputType]=deal('SingleEndedNonReferenced');
      end
      if any(p.stimCh)
         [s.Channels(p.stimCh).InputType]=deal('SingleEnded');
      end
      [s.Channels.Range]=deal(p.rangeIn);
   end
   if ~isempty(p.niChannelOut)
      s.addAnalogOutputChannel(p.niDevOut, p.niChannelOut, 'voltage');
   end
   if ~isempty(p.niChannelOutTrace)
      s.addAnalogOutputChannel(p.niDevOut, p.niChannelOutTrace, 'voltage');
   end
   if ~isempty(p.OPTOchannel)
      ch = s.addAnalogOutputChannel(p.niDevOut, p.OPTOchannel, 'voltage');
      ch.Range = p.OPTOrange;
      clear ch
   end
end
% SOUNDCARD output
if strcmpi(p.sessionType, 'directsound')
   if ~isempty(p.niChannelOut)
      s.addAudioOutputChannel(p.niDevOut, p.niChannelOut);% add playback channel
   end
   if ~isempty(p.niChannelOutTrace)
      s.addAudioOutputChannel(p.niDevOut, p.niChannelOutTrace);% add LED channel
   end
   if ~isempty(p.niChannelIn)
      s.addAudioInputChannel(p.niDevIn, p.niChannelIn);% add recording channel
   end
end

% add listener if there's any output channel in the current configuration
if ~isempty(p.niChannelOut) |  ~isempty(p.niChannelOutTrace) | ~isempty(p.soundChannelOut)
   lhOut = addlistener(s,'DataRequired',@(src, event)queueMoreData(src, event, handles));
end

% setup external aquisition trigger (for 2P)
if isfield(p, 'externalTrigger') && p.externalTrigger                % `externalTrigger` should be set in the config file - used to coordinate daq and Ca imaging
   try                                                               % if set, wait for an external trigger before starting the data aquisition
      s.ExternalTriggerTimeout = 20;                                 % time out - seconds to wait for the trigger
      s.addTriggerConnection('external','Dev2/PFI0','StartTrigger'); % set the channel on which to listen to the trigger
   end
end
% setup trigger outputs for remote triggering other devices
if isfield(p, 'remoteControl2P') && p.remoteControl2P
   s.addDigitalChannel(p.niDevOut, p.niRemoteStart, 'OutputOnly');
   s.addDigitalChannel(p.niDevOut, p.niRemoteStop,  'OutputOnly');
   s.addDigitalChannel(p.niDevOut, p.niRemoteNext,  'OutputOnly');
end

s.Rate = p.Fs;
s.IsContinuous = true;
s.IsNotifyWhenDataAvailableExceedsAuto = false;
s.NotifyWhenDataAvailableExceeds = p.count;
s.addlistener('DataAvailable',@(src, event)soundCallback(src, event, handles));

%% setup
switch p.video
   case 'matlab'
      v = initMatlabVideo();
   case 'python'
      if isfield(p, 'resetPythonCameras') && p.resetPythonCameras
         disp('  setting up python camera ')
         try
            eval( sprintf('!python %s', which('mpTestZMQ_resetAllCameras.py')) );
         end
      end
   otherwise
      disp('no video mode selected')
end
%% setup gui
disp('  setting up GUI.')
set(handles.startButton,'Value',0);
p.save = 0;
if ~isempty(p.niChannelIn)
   set(handles.popupmenu1, 'String',[{'all'} num2cellstr(p.niChannelIn)']);
   set(handles.popupmenu1, 'Value',2);
end
if ~isempty(p.niChannelOut)
   % populate control file list...
   ctrlFiles = dir(fullfile(p.ctrlDir, '*.txt'));              % parse CTRL directory for control files (need to end with '.txt')
   set(handles.popupmenu3,'String',{ctrlFiles.name})            % populate list with names of control files
   set(handles.popupmenu3,'Value',1)                           % select first control file on the list
   popupmenu3_Callback(hObject, eventdata, handles);           % call CTRL FILE SELECTOR playback to load first control file into playlist
end

p.sessionID = get(handles.edit1, 'String')
p.pauseToggle = 0;
% set RANDOMIZE stimulus order state
if p.stimOrderRandom
   set(handles.checkbox3, 'Value', 1);
else
   set(handles.checkbox3, 'Value', 0);
end
%% LED
% if there's any output channel defined then LED is on whenever stim is on
% w/o playback output: blink LED at fixed rate
if isempty(p.niChannelOut) && ~isempty(p.niChannelOutTrace)
   p.stimTrace{1} = p.LEDamp*[ones(s.Rate*2,1);zeros(s.Rate*1,1)];% end with 0 so it LED ends with OFF state (1 on 29 off for one sec out of 1/2 min)
   p.stimAll{1} = [];
   p.stimFileName{1} = 'LED trace';
end
% define LED pattern for optogenetics - this could come from a file...
if ~isempty(p.OPTOchannel)
   disp('   setting up OPTOGENETICS')
   switch p.optoType
      case 0 % courtshipOpto
         fr = 100; %Frequency in Hz. For example: 100Hz = 5ms ON, 5ms OFF in one period
         pulseTrain = p.OPTOamp*(1+square((1/s.Rate:1/s.Rate:3)*(2*pi*fr)))/2;
         pulseTrain(end) = 0;
         p.stimAll{1} = pulseTrain';
      case 1 % courtshipOpto_Talmo
         cycleDur = 3;
         pulseLength = cycleDur*s.Rate;
         pulseTrain = p.OPTOamp*ones(pulseLength, 1);
         %             pulseTrain(end) = 0;
         p.stimON = pulseTrain;
         p.stimOFF = zeros(size(pulseTrain));
         p.stimAll{1} = p.stimON;
      otherwise
   end
   
end

%% remote-controlled light switch
if isfield(p,'controlLights') && p.controlLights
   disp('initializing light control')
   try
      p.a = arduino();
      p.pinOn = 'D3';
      p.pinOff = 'D5';
      
      p.a.configurePin(p.pinOn,  'DigitalOutput');
      p.a.configurePin(p.pinOff, 'DigitalOutput');
      p.a.writeDigitalPin(p.pinOff, 0);
      p.lightON  = @()p.a.writeDigitalPin(p.pinOn, 1);
      p.lightOFF = @()p.a.writeDigitalPin(p.pinOn, 0);
   catch ME
      disp(ME.getReport())
      warning('something went wrong - setting REMOTE LIGHT CONTROL to OFF')
      p.controlLights = false
   end
end

%%

% for saving recorded data
% NIdaq gets 16bit data - saving this as double is a waste of memory and
% disk space - so we save as int16 after scaling the data up to exploit all
% 16 bits of resolution - this is the scaling factor used:
p.dataScalingFactor = 1000*floor(0.9*double(intmax('int16'))/max(abs(p.rangeIn))/1000);

% Choose default command line output for prvGreyPlayback4
handles.output = hObject;                                   % Update handles structure
set(handles.startButton,'Enable','on')
set(handles.exitButton,'Enable','on')
guidata(hObject, handles);

disp('done!')

function queueMoreData(src,event, handles)
% this is called when the output process needs more data...
global p s

channelOrder = argsort([p.niChannelOut p.OPTOchannel p.niChannelOutTrace]);

% if p.pauseToggle
%    disp('1sec of silence')
%    nOutChannels = length(channelOrder);
%    if isfield(p, 'remoteControl2P') && p.remoteControl2P
%       nOutChannels = nOutChannels + 3;
%    end
%    s.queueOutputData( zeros(s.Rate, nOutChannels));
%    return
% end

p.stiCnt = p.stiCnt + 1;
p.sti(p.stiCnt) = p.stimOrder( p.stiCnt );

% stop opto after i cycles (a cycle is 3 seconds, so for example 100 cycles are 5 minutes)
elapsedTime = p.stiCnt * 3; % secs
% disp(elapsedTime)
if ~isempty(p.OPTOchannel)
   switch p.optoType
      case 0 % courtshipOpto
         
         if elapsedTime > p.startOptoTime
            p.stimAll{p.sti(p.stiCnt)} = 0.*p.stimAll{p.sti(p.stiCnt)};
         end
      case 1 % courtshipOpto_Talmo
         if mod(elapsedTime, 60) < 30
            % ON
            p.stimAll{p.sti(p.stiCnt)} = p.stimON;
            %                 disp('on')
         else
            % OFF
            p.stimAll{p.sti(p.stiCnt)} = p.stimOFF;
            %                 disp('off')
         end
      otherwise
   end
end

p.stiStart(p.stiCnt,:) = clock;
if isfield(p, 'ctrl')
   disp(p.ctrl.stimFileName{p.sti(p.stiCnt)})
   stimMatrix = [p.stimAll{p.sti(p.stiCnt)} p.stimTrace{p.sti(p.stiCnt)}];
   set(handles.popupmenu2,'Value',p.sti(p.stiCnt))                                       % ...and select first stimulus
elseif ~isempty(p.OPTOchannel) % this condition added by Talmo (8/07/2016) -- remove if bugged (p.ctrl wasn't getting filled in)
   stimMatrix = [p.stimAll{p.sti(p.stiCnt)} p.stimTrace{p.sti(p.stiCnt)}];
else
   stimMatrix = [p.stimTrace{p.sti(p.stiCnt)}];
end

% for remote controlling the 2P
triggerTraces = zeros(size(stimMatrix,1),0); % init empy
if isfield(p, 'remoteControl2P') && p.remoteControl2P
   triggerTraces = zeros(size(stimMatrix,1),3);
   if p.stiCnt==1 % for first stim - send only start trigger
      triggerTraces(1:5,1) = 1;% START trigger
      disp('sending START')
   else % all subsequent stims send both triggers
      triggerTraces(1:5,1) = 1;% START trigger
      triggerTraces(6:10,3) = 1;% NEXT file trigger
      disp('sending NEXTFILE')
   end
end
% need to figure out order of DIGITAL outputs? come after aouts?
s.queueOutputData([stimMatrix(:, channelOrder) triggerTraces]);

% log - only when playback
if isfield(p, 'ctrl')
   p.stiStartSample(p.stiCnt+1) = p.stiStartSample( limit(p.stiCnt, 1, inf) ) + size(stimMatrix,1);
   p.log = [p.log;...
      [p.ctrl(p.sti(p.stiCnt),:)...
      table(p.stiStartSample(p.stiCnt), 'VariableNames', {'sample'})]
      ];
end
% --- Outputs from this function are returned to the command line.
function varargout = prvGreyPlayback4_OutputFcn(hObject, eventdata, handles)
varargout{1} = handles.output;

function popupmenu1_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
   set(hObject,'BackgroundColor','white');
end

% --- Executes on selection change in popupmenu1.
function popupmenu1_Callback(hObject, eventdata, handles)
%% ------------------------------------------------------------------------- START RECORDING

function soundCallback(src,evt, handles)
%% ------------------------------------------------------------------------- PROCESS SOUND RECORDING
% this is called whenever any data from inputs is available
% we plot data here and collect data into a big matrix
global p

% PLOTTING
p = p.plotDataFunction(evt, handles, p);

% COLLECTING DATA in p.data
if p.save
   p.data(p.maxTime + (1:size(evt.Data,1)),:) = int16(p.dataScalingFactor*evt.Data(:,~p.temperatureChannel));
   p.maxTime = p.maxTime + size(evt.Data,1);
   if evt.TimeStamps(end)>p.maxRecordingTime % stop automatically
      disp('entering stop')
      startButton_Callback(handles.startButton, evt, handles);
   end
   % save temperature channel separately
   if any(p.temperatureChannel)
      p.temperatureCount = p.temperatureCount + 1;
      p.temperatureVolt(p.temperatureCount) = mean(evt.Data(:,p.temperatureChannel));
      p.temperatureTime(p.temperatureCount) = evt.TimeStamps(1);
   end
end

function videoCallback(src,evt,handles)
% ------------------------------------------------------------------------- PROCESS VIDEO RECORDING
% this is called whenever a frame is available...
global p v
persistent time
persistent metadata
[~, time, metadata] = getdata(v,get(v,'FramesAvailable'));
if p.save && ~isempty(metadata)
   p.frameNumber = max([metadata.FrameNumber]);
   p.frameTimes([metadata.FrameNumber]) = time;
   p.frameAbsTimes(p.frameNumber,:) = [metadata(end).AbsTime];
   %display fps
   if mod(p.frameNumber,6)==1 && p.frameNumber>100
      set(handles.FPSCount, 'String',[num2str(1/mean(diff(p.frameTimes...
         (p.frameNumber-100:p.frameNumber))), '%1.2f') ' fps ']);
   end
end

% --- Executes on button press in exitButton. ---------------------------- EXIT
function exitButton_Callback(hObject, eventdata, handles)
% clean up daq and video
global v vFile p
set(handles.startButton,'Enable','off')
set(handles.exitButton,'Enable','off')
set(handles.exitButton,'String','Exiting');
try
   daqreset()
   switch p.video
      case 'matlab'
         closepreview(v);
         close(v.DiskLogger);
         close(vFile);
         imaqreset()
         %       case 'python'
         %          sendMessage_cam('STOP', p.portsMatlab, p.camID)
   end
catch ME
   disp(ME.getReport())
end
if isfield(p,'controlLights') && p.controlLights
   p.lightOFF();
end
p.exit = 1; % so we now when we restart that the session was exited
clear p;
close all;

% --- Executes on button press in startButton. ---------------------------- START/STOP SAVING
function startButton_Callback(hObject, eventdata, handles)
global p s  v vFile
set(handles.startButton,'Enable','off')
set(handles.exitButton,'Enable','off')
p.save = get(handles.checkSave, 'Value');
p.run = strcmp(get(handles.startButton, 'String'), 'Start');

% determine which stimuli to play
if get(handles.checkbox4, 'Value')
   p.selectedStimulus = get(handles.popupmenu2,'Value');% get selected stimulus
else
   p.selectedStimulus = 1:length(p.stimAll);% selected all stimuli
end
if ~isempty(p.niChannelOut)
   p.ctrl.stimFileName(p.selectedStimulus)
   % !!!!
   stimPerRecording = ceil((p.maxRecordingTime*s.Rate)/mean(cellfun(@(x)size(x,1),p.stimAll(p.selectedStimulus))))+length(p.stimAll(p.selectedStimulus));
   p.stimOrder = repmat(1:length(p.stimAll(p.selectedStimulus)), 1, ceil(stimPerRecording/length(p.stimAll(p.selectedStimulus))));
   % !!!!
else
   p.stimOrder = ones(100000,1);
end
% check randomize status
if get(handles.checkbox3, 'Value')
   p.stimOrder = p.stimOrder( randperm(length(p.stimOrder)) );
end

if p.run
   disp('entering RUN')
   if isfield(p,'controlLights') && p.controlLights
      p.lightON();
   end
   set(handles.startButton,'BackgroundColor','r')
   % initialize data structures
   if strcmpi(p.video, 'matlab')
      p.frameTimes = zeros(ceil(1.1*p.maxRecordingTime*p.FPS),1);
      p.frameAbsTimes = zeros(ceil(1.1*p.maxRecordingTime*p.FPS),6);
   end
   p.data = zeros(ceil(1.1*p.maxRecordingTime*s.Rate),sum(~p.temperatureChannel),'int16');
   p.maxTime = 0;
   if any(p.temperatureChannel)
      p.temperatureCount = 0;
      p.temperatureVolt = zeros(1.1*10*p.maxRecordingTime,1);
      p.temperatureTime = zeros(1.1*10*p.maxRecordingTime,1);
   end
   p.stiStartSample = zeros(length(p.stimOrder),1);
   p.log = [];
   
   p.frameNumber = 0;
   p.stiCnt = 0;
   p.sti = 1;
   if strcmpi(p.video, 'python')
      for pp = 1:length(p.portsPython)
         pythonCmd = sprintf('!python %s --cam_id %d --frontend_port %d --backend_port %d --ip_address %s --frame_rate %d --frame_size_color %s --roi %s & exit &', ...
            which(p.pythonCameraCommand), p.camID(pp), p.portsMatlab(pp), p.portsPython(pp), p.ipAddress, p.frameRate, p.frameSizeColor, p.roi );
         %          disp(pythonCmd)
         eval(pythonCmd)
      end
   end
   % Reset output channels (turns off LEDs before starting)
   numOutCh = numel([p.niChannelOut, p.OPTOchannel, p.niChannelOutTrace]);
   if isfield(p, 'remoteControl2P') && p.remoteControl2P
      numOutCh = numOutCh+3;
   end
   s.outputSingleScan(zeros(1, numOutCh));
   
   disp(['   stopping in ' num2str(p.maxRecordingTime/60,'%1.2f') ' minutes.'])
   if p.save
      disp('   saving to')
      if ~isfield(p, 'fileNameGenerator')
         p = fileName_date(p);
      else
         p = p.fileNameGenerator(p);
      end
      disp(['   ' p.fName])
      mkdir(fileparts(p.fName))
      switch p.video
         case 'matlab'
            vFile = VideoWriter([p.fName '.mp4'], p.videoCompress);
            set(vFile,'FrameRate',p.FPS, 'Quality', 100);
            set(v,'LoggingMode','disk&memory');
            set(v,'DiskLogger',vFile);
         case 'python'
            sendMessage_cam(['START' p.fName], p.portsMatlab, p.camID)
            if isfield(p, 'delayAfterStartingVideo')
               fprintf('Sent video start command. Starting acquisition in %d secs...\n', p.delayAfterStartingVideo)
               pause(p.delayAfterStartingVideo);
            end
      end
      
      if exist([p.fName '.mat'], 'file')
         disp(['overwriting' p.fName])
         delete([p.fName '.mp4']);
         delete([p.fName '.mat']);
      end
      
   else
      % added this to avoid overwriting files
      switch p.video
         case 'matlab'
            set(v,'LoggingMode','memory');
         case 'python'
            sendMessage_cam('TEST', p.portsMatlab, p.camID)%
      end
      
   end
   if strcmpi(p.video, 'matlab') && p.showPreview
      preview(v);
   end
   %% run
   set(handles.startButton,'String','Stop');
   
   if ~isempty(p.niChannelOut) || ~isempty(p.niChannelOutTrace)
      queueMoreData([],[], handles);
   end
   s.prepare();
   if strcmpi(p.video, 'matlab')
      start(v);
   end
   pause(0.5);
   s.startBackground;
else
   disp('   stopping:')
   disp('      daq')
   
   % stop aquisition
   s.stop()
   % send STOP trigger to 2P -for remote controlling the 2P
   if isfield(p, 'remoteControl2P') && p.remoteControl2P
      numOutCh = numel([p.niChannelOut, p.OPTOchannel, p.niChannelOutTrace]);
      triggerTraces = zeros(1, numOutCh+3);
      triggerTraces(:,end-1) = 1;% set STOP trigger
      disp('sending STOP')
      s.outputSingleScan(triggerTraces );
   end
   % stop frame grabber and preview
   switch p.video
      case 'matlab'
         disp('      preview')
         stoppreview(v)
         disp('      frame grabber')
         stop(v)
      case 'python'
         disp('sending stop to python video')
         if isfield(p, 'delayForStoppingVideo')
            pause(p.delayForStoppingVideo)
         end
         sendMessage_cam('STOP', p.portsMatlab, p.camID)
   end
   
   if p.save
      if strcmpi(p.video, 'matlab')
         % wait for disk logger to save all frames
         cnt = 0;
         while(cnt<10 && v.DiskLoggerFrameCount~=v.FramesAcquired)
            if cnt==0
               fprintf('   waiting for disklogger')
            end
            pause(1);
            fprintf('.')
            cnt = cnt+1';
         end
         videoCallback([],[],handles);
         % keep only acquired data
         p.frameTimes = p.frameTimes(1:p.frameNumber);
         disp('      disk logger')
         close(v.DiskLogger);
         close(vFile)
      end
      
      if any(p.temperatureChannel)
         p.temperatureVolt = p.temperatureVolt(1:p.temperatureCount);
         p.temperatureTime = p.temperatureTime(1:p.temperatureCount);
      end
      
      logs.fStrain = 'NA';
      
      p.data = p.data(1:p.maxTime,:);
      
      if isfield(p, 'createVirtualLEDrecording') && p.createVirtualLEDrecording
         disp('   adding virtual LED trace recording...')
         tmp = repmat(p.stimTrace{1}, ceil(size(p.data,1)/length(p.stimTrace{1})),1);
         p.data(:,p.stimCh) = tmp(1:size(p.data,1));
      end
      
      % save analog input data
      disp('      saving recorded data (may take some time).')
      data = p.data;
      p.data = [];
      dataScalingFactor = p.dataScalingFactor;
      INFO = {'Inputs recorded as double, scaled and saved as INT16.';...
         'To recover original data cast 1) to double and 2) divide by DATASCALINGFACTOR';...
         'Like so: `data = double(data)./dataScalingFactor;`'};
      respCh = p.respCh;
      stimCh = p.stimCh;
      save([p.fName 'bin'],'data','dataScalingFactor','respCh','stimCh','INFO');
      % save parameter structure and frame times and temperature and and and
      rDat = p;
      try
         rDat = rmfield(rDat,{'data', 'a', 'lightON','lightOFF', 'plotDataFunction','fileNameGenerator'});
      end
      rDat.channelsAll = rDat.respCh;
      rDat.channels = rDat.respCh(~rDat.temperatureChannel);
      [~, fNam, ~] = fileparts(rDat.fName);
      rDat.fName = [fNam, '.mat'];
      save([p.fName 'vDat'], 'rDat','logs');
      disp('   done.')
      
      % write log file - only for playback
      if isfield(p, 'ctrl')
         writetable(p.log, [p.fName 'log.txt'], 'FileType', 'text', 'Delimiter', '\t');
      end
   end
   
   % reset frame counters
   p.frameNumber = 0;
   if strcmpi(p.video, 'matlab')
      p.frameTimes = zeros(ceil(1.1*p.maxRecordingTime*p.FPS),1);
      p.frameAbsTimes = zeros(ceil(1.1*p.maxRecordingTime*p.FPS),6);
   end
   % update gui
   set(handles.startButton,'BackgroundColor','g')
   set(handles.startButton,'String','Start');
   set(handles.exitButton,'Enable','on')
   if isfield(p,'controlLights') && p.controlLights
      p.lightOFF();
   end
end
set(handles.startButton,'Enable','on')

% --- Executes on button press in checkSave.
function checkSave_Callback(hObject, eventdata, handles)
if get(handles.checkSave, 'Value');
   disp('saving ON')
else
   disp('saving OFF')
end

function startButton_ButtonDownFcn(hObject, eventdata, handles)


% --- Executes on selection change in popupmenu2.                          LOAD AND PREPARE STIMULUS
function popupmenu3_Callback(hObject, eventdata, handles)
global p s;
if ~isempty(p.niChannelOut)
   ctrlFileNames = cellstr(get(handles.popupmenu3,'String'));              % get names of ctrl files from GUI list
   disp(['loading control file: ' ctrlFileNames{get(handles.popupmenu3,'Value')}])
   p.ctrl = readCtrlFile( fullfile(p.ctrlDir, ctrlFileNames{get(handles.popupmenu3,'Value')}) );  % load ctrl file that is currently selected in GUI
   disp(p.ctrl)
   set(handles.popupmenu2,'String',p.ctrl.stimFileName)                    % ...and populate playlist list with stimFileNames from current control file
   set(handles.popupmenu2,'Value',1)                                       % ...and select first stimulus
   
   % LOAD or GENERATE ALL STIM in ctrlFile
   p.stimAll = {}; % reset stimulus list
   for sti = 1:length(p.ctrl.stimFileName)                                 % get current stimulus from playlist
      p.sti = sti;
      p = loadStim(p);
      [p, s] = attenuateStim(p, s);                                        % ATTENUATE STIM
      p.stimAll{p.sti} = p.stim;
      
      if ~isempty(p.niChannelOutTrace) && p.LEDmirrorsSound
         stimLen = length(p.stim) - round(p.ctrl.silencePre(p.sti)/1000*s.Rate) - round(p.ctrl.silencePost(p.sti)/1000*s.Rate);
         p.stimTrace{p.sti} = p.LEDamp*[zeros(round(p.ctrl.silencePre(p.sti)/1000*s.Rate),1); ones(stimLen,1); zeros(round(p.ctrl.silencePost(p.sti)/1000*s.Rate),1)]; % add silence to the beginning and end of the stimulus (from CTRL file)
      else
         p.stimTrace{p.sti} = [];
      end
   end
else
   disp('no output channels...')
end
guidata(hObject, handles);


% --- Executes during object creation, after setting all properties.
function popupmenu2_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
   set(hObject,'BackgroundColor','white');
end

% --- Executes during object creation, after setting all properties.
function popupmenu3_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
   set(hObject,'BackgroundColor','white');
end

function popupmenu2_Callback(hObject, eventdata, handles)

% --- Executes on selection change in popupmenu4.  --- LOAD NEW USER
function popupmenu4_Callback(hObject, eventdata, handles)
global p
disp('reloading config')
prvGreyPlayback4_OpeningFcn(hObject, eventdata, handles, p.configFileName)

% --- Executes during object creation, after setting all properties.
function popupmenu4_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
   set(hObject,'BackgroundColor','white');
end



% _________ RANDOMIZE ________________
% --- Executes on button press in checkbox3.
function checkbox3_Callback(hObject, eventdata, handles)
% Hint: get(hObject,'Value') returns toggle state of checkbox3
if get(hObject,'Value')
   disp('  randomized-order playback')
else
   disp('  fixed-order playback')
end


% _________ SESSION NUMBER ________________
function edit1_Callback(hObject, eventdata, handles)
global p
p.sessionID = get(hObject, 'String');

% --- Executes during object creation, after setting all properties.
function edit1_CreateFcn(hObject, eventdata, handles)
% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
   set(hObject,'BackgroundColor','white');
end


% --- PAUSE
function pushbutton3_Callback(hObject, eventdata, handles)
global p
p.pauseToggle = ~p.pauseToggle;
if p.pauseToggle
   set(hObject, 'String', 'PAUSED')
else
   set(hObject, 'String', 'pause')
end

% PLAY SEL STIM ONLY
function checkbox4_Callback(hObject, eventdata, handles)
% Hint: get(hObject,'Value') returns toggle state of checkbox4
if get(hObject,'Value')
   disp('  playing SELECTED stimulus only')
else
   disp('  playing ALL stimuli in playlist')
end

