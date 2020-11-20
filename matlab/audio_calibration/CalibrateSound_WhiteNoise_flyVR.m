%calibration code for auditory song delivery

%This procedure is shortly described in Tootoonian S. et al., 2012
%(https://www.jneurosci.org/content/32/3/787.long#ref-24), under 'Sound
%delivery system and calibration', using
%https://www.bksv.com/media/doc/Bp0100.pdf (4133)

%This script saves mean_ifft_tf_micToStim whech is the transfer
%function from the microphone output to the stimulus input. Multiplying this function makes sure that 
%when white noise stimulus is played, it will be flat (same amplitude for
%all frequencies) to the fly (near the tube output)

%% parameters
attenuationFolder = 'C:\Users\Lab Admin\Dropbox\Diego\prvDaq.jan\daq\attenuation'; % Here the the attenuation and transfer function files are saved
New_transfer_File = fullfile(attenuationFolder,['transferFunction_',datestr(date,'yyyymmdd')]);
New_WN_File = fullfile(attenuationFolder,['WhiteNoise_',datestr(date,'yyyymmdd')]);

%White noise stimulus
NumberOf_WhiteNoisestim = 5;% generate this number of white noise stimuli
Repeats_Per_WhiteNoisestim = 10; % play each stim this number of times
Fs = 44100;     % Stimulus sampling rate (Hz) - sound card
F1 = 80;        % band pass filder - lower cutoff
F2 = 1000;      % band pass filder - upper cutoff
T = 4.5;        % duration of noise stimulus (s)
startCut = 2;   % start offset in seconds (stimulus to use for calibration, out of the T that was played)
timeTaken = 2;  % seconds of stimulus to play (/use for calculating the transform function)

%Stimulus recording (DAQ)
sps = 44100; % recording sampling rate on DAQ

%% Generate and save white noise (WN) stimuli: NumberOf_WhiteNoisestim different WN stimuli, repeat each one Repeats_Per_WhiteNoisestim times
ff = getFilt(F1, F2, Fs); % define bandpass filter
stim_ = zeros(NumberOf_WhiteNoisestim,T*Fs); %define bandpass filter
% generate white noise NumberOf_WhiteNoisestim times
for nStim = 1:NumberOf_WhiteNoisestim
    Y = rand(1, T*Fs); % white noise signal
    stim = filter(ff, Y); % band-pass filtered white noise
    stim_(nStim,:) = stim;
end

stim_ = repmat(stim_,Repeats_Per_WhiteNoisestim,1); % generate white noise NumberOf_WhiteNoisestim times

% save white noise
fprintf('saving pulse train to:\n   %s.mat\n', New_WN_File)
save(New_WN_File, 'stim_');


%% play and save - white noise using flyVR
%play the white noise stimuli one by one using the sound card using flyVR. The data will be recorded in the
%DAQ, in the Mic_Calibration_Ch channel

% ##missing code##
% ##missing code##
% ##missing code##

%temp
mic_ = stim_;
%temp

%% Prepare stim_ and mic_ before calculating the transfer functions
cutIdx = startCut*Fs + (1:timeTaken*Fs);
stim_ = stim_(:,cutIdx);
mic_ = mic_(:,cutIdx);

% highpass filter to revome low frequency noise in microphone recording in mic_ using butterworth 
n = 8; % nth-order lowpass digital Butterworth filter
cutoff_frequency = 80; % Hz
Wn = cutoff_frequency/(sps/2); %normalized cutoff frequency
[b, a] = butter(n, Wn, 'high');%high pass

for trial = 1:size(mic_,1)
    hpf = filtfilt(b, a, mic_(trial,:));
    mic_(trial,:) = -1*hpf; % multiply by -1 because the phase got reversed (maybe by the filter?)
end

% Normalization
for trial = 1:size(mic_,1)%stim_ is the same size
    % normalize amp of both stim and rec
    maxV = max(abs(stim_(trial,:)));
    stim_(trial,:) = stim_(trial,:)/maxV;
    
    maxV = max(abs(mic_(trial,:)));
    mic_(trial,:) = mic_(trial,:)/maxV; 
end

%% Calculate and transfer functions for white noise
numTrials = size(stim_,1);%stim_ and mic_ has the same dimentions


[mean_ifft_tf_stimTomic, ...
    mean_ifft_tf_micToStim, tf] = ...
    get_transfer_funct(stim_, mic_, Fs, numTrials);

% plot power spectrum of input and recorded auditory stimulus
plot_pwelch_per_trial(stim_, mic_, Fs, numTrials, tf)

[mean_ifft_tf_stimTomic, mean_ifft_tf_micToStim, tf] = ...
    get_transfer_funct(stim_, mic_, Fs, numTrials)

%% save transfer function 
save([AttenuationFolder date '_transferFunction.mat'], ...
    'mean_ifft_tf_micToStim');

function oFilter = getFilt(F1, F2, Fs)
% ff: function that generates filters
%
% Usage:
%   ff = getFilt(F1, F2, Fs)
%
% Args:
%   F1: lower cutoff
%   F2: upper cutoff
%   FS: Sampling Frequency

N      = 500;  % Order
Wstop1 = 1;    % First Stopband Weight
Wpass  = 1;    % Passband Weight
Wstop2 = 1;    % Second Stopband Weight

% Calculate the coefficients using the FIRLS function
b  = firls(N, [0 F1 F1 F2 F2 Fs/2]/(Fs/2), [0 0 1 1 0 ...
    0], [Wstop1 Wpass Wstop2]);
oFilter = dfilt.dffir(b);

end


function plot_pwelch_per_trial(stim_, mic_, ...
    Fs, numTrials, tf)
% plot_pwelch_per_trial: plot power spectrum of input and recorded
%   auditory stimulus
%
% Usage:
%   plot_pwelch_per_trial(stim_, mic_, ...
%       Fs, numTrials, tf)
%
% Args:
%   stim_: auditory input 
%   mic_: microphone recording
%   Fs: sampling rate of recordings (assumes they are the same)
%   numTrials: max number of trials to load
%   tf: transfer function settings

figAll = figure('name', ...
    'All trials plotted, input stimulus and recorded mic');
hold on

for trial = 1:numTrials
   
   % plot stim and voltage
   figure(figAll)
   
   [psd_stim, fStim] = pwelch(stim_(trial,:), ...
       tf.windowPW, tf.noOverlapPW, tf.NFFT, Fs);
   phs = plot(fStim, 10*log10(psd_stim), 'b-');
   set(phs, 'tag', num2str(trial))
   
   [psd_mic, fVolt] = pwelch(mic_(trial,:), ...
    tf.windowPW, tf.noOverlapPW, tf.NFFT, Fs);

   % divide by frequency if velocity mic used
   % psd_mic = psd_mic./([1:length(fVolt)]');
   
   phv = plot(fVolt, 10*log10(psd_mic), 'k-');
   set(phv, 'tag', num2str(trial))
   
   disp(['Trial ',num2str(trial), ...
       ' done (transfer function,...).'])

end

legend([phs, phv], {'stim', 'resp'})

end

function [mean_ifft_tf_stimTomic, ...
    mean_ifft_tf_micToStim, tf] = ...
    get_transfer_funct(stim_, mic_, Fs, numTrials)
% get_transfer_funct: generates transfer function from auditory stimuli 
%   (input vector in matlab) to microphone recording (volt) and vice versa.
%
% Usage:
%   [mean_ifft_tf_stimTomic, ...
%       mean_ifft_tf_micToStim] = ...
%       get_transfer_funct(stim_, mic_, Fs, numTrials)
%
% Args:
%   stim_: auditory input 
%   mic_: microphone recording
%   Fs: sampling rate of recordings (assumes they are the samefor both stim_ and mic_)
%   numTrials: max number of trials to load

% default settings
% 2^nextpow2(size(voltageScaled,2));
tf.NFFTTF = 10000;% This is the "sampling points to calculate the discrete Fourier transform" and as it is in the frequency
%domain, it probably doesn't change when moving from 10000 (what we used with DAQ) to 44100 (sound card)

% window for pwelch
tf.windowPW = 1000;
tf.noOverlapPW = tf.windowPW/2;

% window for tfestimate
tf.windowTF = 5000;%change from 10000/2 to 44100/2?
tf.noOverlapTF = tf.windowTF/2;

for trial = 1:numTrials
   
   % Calculate transfer function between the original stimulus
   % and the microphone output using tfestimate (matlab built-in function)
   tf_stimTomic(trial, :) = tfestimate(stim_(trial, :), ...
       mic_(trial, :), tf.windowTF, tf.noOverlapTF, tf.NFFTTF, Fs, 'twoside');
   
   tf_micToStim(trial, :) = tfestimate(mic_(trial, :), ...
       stim_(trial, :), tf.windowTF, tf.noOverlapTF, tf.NFFTTF, Fs, 'twoside');   
   
   % calculate the ifft to transformeach TF to frequency domain
   ifft_tf_stimTomic(trial, :) = ifft(tf_stimTomic(trial, :), tf.NFFTTF);
   ifft_tf_micToStim(trial, :) = ifft(tf_micToStim(trial, :), tf.NFFTTF);
   
   disp(['Trial ',num2str(trial),' done (transfer function,...).'])
   
end

mean_ifft_tf_stimTomic = circshift(...
    mean(ifft_tf_stimTomic, 1), [0 tf.NFFTTF/2]);
mean_ifft_tf_micToStim = circshift(...
    mean(ifft_tf_micToStim, 1), [0 tf.NFFTTF/2]);

end



