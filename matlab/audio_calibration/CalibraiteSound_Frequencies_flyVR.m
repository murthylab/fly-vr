
% for calibrating the sound delivery for either pure tone of white noise(WN)
% For pure tones: find the scalar to convert from value in the code (volts) to mm/sec
% For WN: after the reverse transform was calculated (by a separate functiopn) - find the one scalar to move from volts to mm/sec


% This script is a pseudo code - needs to be translated to python in flyVR2.0
% this scripts takes the microphone recording and calculates the playback's 


%parameters
WN = 0; % are we playing white noise data (WN = 1) or pure tones (WN = 0)
%If WN  = 1 - need to find only one velue: a scale from WN arbitrary units to
%mm/sec. If WN = 0 - need to find an attenuation value for each frequency in the list
%WN_ToPlay = ...need to generate or read from a file
chn = 1;                % Sound card channel to calibrate; if >1 channel, repeat for each channel
targetInt = 3; % this is how loud it should be (in mm/sec)
partVelVoltChannel = 3; % DAQ AI channel for recording the sound from the microphone amplifier


attenuationFolder = 'C:\Users\Lab Admin\Dropbox\Diego\prvDaq.jan\daq\attenuation\';

attenuationSineFile_Old = fullfile(attenuationFolder,'attenuation20170307_Ca.txt');%old attenuation file
attenuationSineFile_New = fullfile(attenuationFolder,'attenuation20201107_Ca.txt');%new attenuation file to save
if WN == 1%otherwise - do not need this file
TransferFunction = 'C:\Users\Lab Admin\Dropbox\Diego\prvDaq.jan\daq\attenuation\cal20120913_transferFunction.mat';    
end

tOldAtt = readtable(attenuationSineFile_Old);
tNewAtt = tOldAtt;%default - but will be updated
Freq_ToPlay = tOldAtt.freq(1:end-1);

% DO NOT CHANGE - stuff specific to the microphone calibration
micAmpGain = 20; % amplification factor of the microphone amplifier (must be set to 20dB !)
convFactor_file = fullfile(attenuationFolder,'convFactor_20msec_Mic1.mat');
load(convFactor_file)  % calibration data for the mic: must have this file!
convFactor = c;

windowToAnalyze = [5000 6000]; % sample range to analyze
Ft = 44100;%frame rate (samples per second; 44100 for sound card)


%% for each frequency, play, record, calculate attecuation

%consider - runnig 2-3 times to converge to the the right attenuation values
for nFreq = Freq_ToPlay

% #####missing code####
% Generate stimulus (pure tone) using attenuationSineFile_Old
% play sound - one second pure tone in each loop - record and save
% partVelVolt =  % the RAW recorded voltage (vector)
% display while delivering (figure 1).
% perhaps go over all the tones in both 
% #####missing code####


%%
vel = particleVelocity(partVelVolt, windowToAnalyze, convFactor, Ft, micAmpGain, WN);
meanVel = mean(vel); % this is how loud it actually is - mean vel over the sample range

attFreqIdx = nFreq; % stimulus frequency played

%update the attenuation value for this frequency
if chn == 1
oldAtt = tOldAtt.attenuation(nFreq);  % current attenuation factor !! modify based on attenuationSineFile_Old
newAtt = targetInt.*oldAtt./meanVel; % new attenuation factor
tOldAtt.attenuation(nFreq) = newAtt;
elseif chn == 2
oldAtt = tOldAtt.attenuation_1(nFreq);
newAtt = targetInt.*oldAtt./meanVel; % new attenuation factor
tOldAtt.attenuation_1(nFreq) = newAtt;
end

newAtt = targetInt.*oldAtt./meanVel; % new attenuation factor

% as far as I understand, for white noise after multiplying by the reverse
% transfer fanction that was previously calculated, this should be +-flat,
% so +- same newAtt for each frequency

mNewAtt(nFreq, 1) = nFreq;
mNewAtt(nFreq, chn+1) = newAtt;%columns 2,3 for channels 1,2

% display results:
figure(2)
disp(['stim intensity @' num2str(p.ctrl.freq{p.sti}(chn),'%1.2f') 'Hz:'])
disp(['   target: ' num2str(targetInt,'%1.2f') 'mm/s, is: ' num2str(meanVel,'%1.2f') 'mm/s'])
disp('attenuation factor:')
disp(['   old: ' num2str(oldAtt,'%1.4f') 'mm/s, new: ' num2str(newAtt,'%1.4f') 'mm/s'])

%uncheck the next 2 lines when you like to see the new values at the end of calibration
% disp('setting new attenuation factor.')
% p.attenuation.attenuation(attFreqIdx, chn) = newAtt;
% 
if nFreq == Freq_ToPlay(end) % after going over all tones, list new and old attenuation factors
   disp([p.attenuation.freqs p.attenuation.attenuation])
   disp(p.attenuation.attenuation)
end
disp(' ')

end



function [partVel, freqOfInt] = particleVelocity(partVelVolt,windowToAnalyze,convFactor,Ft,micAmpGain,WN)
% partVelVolt - recording
% windowToAnalyze  - time indices [start end]
% convFactor - struct from file
% Ft - sampling rate [Hz]
% micAmpGain -  from mic amp gain
% wn - true/false or 1/0

plotIt = 1;
window = round(convFactor.window*Ft/1000); % number of sample points (NOT msec!!!), should correspond to that used to calculate conversion factor

pointOfInt_b = windowToAnalyze(1);
pointOfInt_e = windowToAnalyze(2);

for p = 1:length(pointOfInt_b:pointOfInt_e)
   
   pointOfInt = pointOfInt_b + p;
   %    [st, ft] = spectrogram(partVelVolt(pointOfInt-99:pointOfInt+100),window,[],10000,Ft);
   [st, ft] = spectrogram(partVelVolt(pointOfInt-window/2+1:pointOfInt+window/2),window,[],10000,Ft);
   
   if WN
      meanTest = mean(abs(st),2)./ft;
   else
      meanTest = mean(abs(st),2);
   end
   
   freqRange = ft>100 & ft<900;
   respTest(p) = max(meanTest(freqRange));
   freqOfInt(p) = ft(meanTest==respTest(p));
   
   if WN
      partVel(p) = (respTest(p) * convFactor.convFactor * 1000)/micAmpGain;
   else
      partVel(p) = (respTest(p)/freqOfInt(p) * convFactor.convFactor * 1000)/micAmpGain;
   end
   
end

if plotIt
   subplot(2,2,1)
   plot(partVelVolt(pointOfInt_b:pointOfInt_e))
   xlabel('sample points')
   ylabel('Response mic (V)')
   axis('tight')
   subplot(2,2,2)
   plot(freqOfInt)
   xlabel('sample points')
   ylabel('Peak freq (Hz)')
   axis('tight')
   subplot(2,1,2)
   plot(partVel)
   xlabel('sample points')
   ylabel('part velocity(mm/sec)')
   axis('tight')
   drawnow
end

end