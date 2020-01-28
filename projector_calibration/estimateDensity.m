function [lightDensity] = estimateDensity(azimAll, elevAll, xVals, yVals)
    % want to find correspondance between estimate of number of pixels/cm^2
    % eg, if *vals spans a large theta, it should have correspondingly MORE
    % light shown on it

    % how do we calculate that? we want to make a map in radial space of
    % the pixel that corresponds to it on the screen. Then, for a given
    % theta, we can calculate the number of nearby xvals and normalize (the
    % inverse?)
    
    thetaThresh = 30;
    for ii=1:size(azimAll,1)
        for jj=1:size(azimAll,2)
            % find all azim/elevation within radius R of this point
            % and calculate distance (normalized by R) of the pixel-space
            % eg we want dtheta/dR
            
            thetaDist = sqrt((azimAll - azimAll(ii,jj)).^2 + (elevAll - elevAll(ii,jj)).^2);
            nearbyTheta = find(thetaDist < thetaThresh);
            pixelDist = sqrt((xVals(nearbyTheta) - xVals(ii,jj)).^2 + (yVals(nearbyTheta) - yVals(ii,jj)).^2);
            
            dThetadR(ii,jj) = mean(thetaDist ./ pixelDist);
        end
    end
    
    lightDensity = dThetadR;
end