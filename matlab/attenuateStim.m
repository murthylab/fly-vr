function [p, s] = attenuateStim(p, s)
% [p, s] = attenuateStim(p, s)

freq = p.ctrl.freq{p.sti};
for chn = 1:size(p.stim,2)
   if length(freq)>=chn && any(p.stim(:,chn))
      fprintf('   chn%d:\n', chn)
      % limit intensity to for noise and pure tones to avoid clipping
      if freq(chn)>=0
         freqIdx = find(p.attenuation.freqs==freq(chn));                     % find attenuation factor for stim freq
         if isempty(freqIdx)                                                 % linear interpolation for correcting non-calibrated frequencies         
             warning('%1.2f Hz not found in calibration file - interpolating.',freq(chn))
             % ignore first entry since this corresponds to attenuation for noise
             attenuationFactor = interp1(p.attenuation.freqs(2:end), p.attenuation.attenuation(2:end,chn), freq(chn), 'linear');
         else
             attenuationFactor = p.attenuation.attenuation(freqIdx, chn);             
         end
         disp('      scaling by attenuation factor')
         p.stim(:,chn) = p.stim(:,chn)*attenuationFactor;                     % attenuate to 1 mm/s
         
         if freq(chn)==0                                                     % if stim is white noise, conv with transfer function
            disp('      convolving with transfer function')
            transferFunction = p.attenuation.transferFunction;
            if s.Rate~=10000
               transferFunction = resample(p.attenuation.transferFunction,s.Rate,10000);
            end
            p.stim(:,chn) = conv(p.stim(:,chn),transferFunction,'same');
         end
      else
         disp('      no attenuation')                                                  % no attenuation for FREQ<0
      end
      % set intensity according to ctrl file
      p.stim(:,chn) = p.stim(:,chn)*p.ctrl.intensity{p.sti}(chn);
      
      % set output range accordingly to max
      soundChannelRange = max(abs(s.Channels(chn).Range.double));
%       s.Channels(chn).Range = p.rangeOut;
      if max(abs(p.stim(:,chn)))>soundChannelRange
         fprintf('         max stim value is %1.3f\n', max(abs(p.stim(:,chn))))
         fprintf('         SETTING EXTENDED RANGE [-10 10] for channel %d\n', chn)
         try
            s.Channels(chn).Range = [-10 10];
         catch ME
            disp(ME.getReport())
         end
      end
   end
end
