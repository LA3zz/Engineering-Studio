%% 2-D finite element analysis - worked examples (Engineering Studio, Phase 8)
clear all; close all; clc

%% 1. Pratt truss bridge: 4 panels of 3 m, 3 m high, 20 kN at each bottom joint
nodes = [0 0; 3 0; 6 0; 9 0; 12 0; 3 3; 6 3; 9 3];
el = [1 2; 2 3; 3 4; 4 5; 6 7; 7 8; 1 6; 2 6; 3 7; 4 8; 5 8; 2 7; 4 7];
sup = [1 1 1; 5 0 1];
loads = [2 0 -20e3; 3 0 -20e3; 4 0 -20e3];
t = truss2d(nodes, el, 200e9, 2e-3, sup, loads);
fprintf('Truss: max tension %.1f kN, max compression %.1f kN, mid-span drop %.2f mm\n', ...
    max(t.N)/1e3, -min(t.N)/1e3, -1000*t.u(3,2));
figure(1); hold on; scale = 200;
for k = 1:size(el, 1)
    i = el(k, :);
    plot(nodes(i,1), nodes(i,2), 'Color', [0.7 0.7 0.7]);
    plot(nodes(i,1) + scale*t.u(i,1), nodes(i,2) + scale*t.u(i,2), 'b', 'LineWidth', 2);
end
hold off; axis equal; grid on; title('Truss deflection (x200)')

%% 2. Portal frame with a sway load and a distributed roof load
pn = [0 0; 0 4; 6 4; 6 0];
pe = [1 2; 2 3; 3 4];
f = frame2d(pn, pe, 200e9, 5e-3, 8e-5, [1 1 1 1; 4 1 1 1], [2 10e3 0 0], [0 -5e3 0]);
fprintf('Frame: sway %.2f mm, base moments %.1f and %.1f kN m\n', 1000*f.u(2,1), ...
    f.reactions(1,3)/1e3, f.reactions(4,3)/1e3);
disp('Member end moments [start end] (kN m):'); disp(f.M/1e3)

%% 3. Plate with a central hole in tension: stress concentration
plate = plate2d(0.4, 0.2, 0.005, 200e9, 0.3, 60, 30, 'left-roller', 'right', [10e6 0], 0.03);
figure(2); contourf(plate.X, plate.Y, plate.von_mises/1e6, 20); colorbar; axis equal
title(sprintf('von Mises stress (MPa), K_t \\approx %.2f', plate.max_von_mises/10e6))
xlabel('x (m)'); ylabel('y (m)')
