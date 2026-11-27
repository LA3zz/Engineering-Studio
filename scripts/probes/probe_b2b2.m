% Probe B2b-2: expected output in comments
disp(trapz([1 2 3]))              % 4
disp(cumtrapz([1 2 3]))           % 0 1.5 4
disp(interp1([1 2 3],[10 20 30],2.5))  % 25
disp(std([1 2 3 4]))              % 1.2910
disp(median([1 2 3 4]))           % 2.5
disp(abs(fft([1 1 1 1])))         % 4 0 0 0
