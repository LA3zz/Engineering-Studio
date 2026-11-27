% Probe: syntax used by the MECH 322 script. Run with F5 after applying B2b-1.
x = [3 1 2];
[~, idx] = sort(x);
disp(idx)
for i = 1:3
    if x(i) < 2, x(i) = 0; end
end
disp(x)
fprintf('it''s %5.2f\n', pi);
c = {'\theta_1','\theta_2'};
disp(size(c))
disp(poly([2 0; 0 3]))
format short g
close all
disp('probe done')
