%% Lab data and materials - worked example (Engineering Studio, Phase 8)
% Reads a tensile test exported from a test machine (data/tensile_test.csv: two header lines,
% then strain and stress in MPa), finds the mechanical properties and saves a summary table.
clear all; close all; clc

d = readmatrix('data/tensile_test.csv');
strain = d(:, 1); stress = d(:, 2) * 1e6;
r = tensile_test(strain, stress);
fprintf('E = %.1f GPa, Sy (0.2%% offset) = %.0f MPa, Su = %.0f MPa, elongation %.1f %%\n', ...
    r.E/1e9, r.Sy/1e6, r.Su/1e6, 100*r.elongation);

al = material('aluminium');
fprintf('Handbook 6061-T6: E = %.0f GPa, Sy = %.0f MPa, Su = %.0f MPa\n', ...
    al.E/1e9, al.Sy/1e6, al.Su/1e6);

figure(1); plot(100*strain, stress/1e6); hold on
e = linspace(0.002, 0.002 + r.Sy/r.E * 1.3, 20);
plot(100*e, r.E*(e - 0.002)/1e6, '--');                   % 0.2 % offset line
plot(100*(r.Sy/r.E + 0.002), r.Sy/1e6, 'o');
hold off; grid on; xlabel('strain (%)'); ylabel('stress (MPa)')
legend('test data', '0.2% offset', 'yield'); title('Tensile test')

% save the results next to the working folder as a table
T.Property = {'E (GPa)'; 'Sy (MPa)'; 'Su (MPa)'; 'Elongation (%)'};
T.Measured = [r.E/1e9; r.Sy/1e6; r.Su/1e6; 100*r.elongation];
T.Handbook = [al.E/1e9; al.Sy/1e6; al.Su/1e6; 12];
writetable(T, 'tensile_summary.csv');
check = readtable('tensile_summary.csv');
disp(check.Measured')

% fatigue check of a part made from it
n = fatigue_sf(60e6, 40e6, 0.4*r.Su, r.Su);
fprintf('Goodman fatigue safety factor: %.2f\n', n);
