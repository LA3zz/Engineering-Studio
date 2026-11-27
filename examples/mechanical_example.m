%% Mechanical Engineering toolbox - worked examples (Engineering Studio, Phase 8)
clear all; close all; clc

%% 1. Beam: simply supported steel beam with two point loads and its own weight
sec = section_ibeam(0.10, 0.008, 0.20, 0.006);     % I-section [m]
E = 200e9;
r = beam(3, E, sec.Ix, 'simply', [5000 3000], [1 2], 300);
fprintf('Reactions: %.1f N and %.1f N\n', r.reactions(1), r.reactions(2));
fprintf('Max moment %.1f N m at x = %.2f m, max deflection %.2f mm\n', ...
    r.max_moment, r.x_max_moment, 1000*r.max_deflection);
sigma = stress_bending(r.max_moment, sec.c, sec.Ix);
fprintf('Max bending stress %.1f MPa, safety factor %.2f (S_y = 250 MPa)\n', ...
    sigma/1e6, safety_factor(sigma, 250e6));
figure(1);
subplot(3,1,1); plot(r.x, r.V); grid on; ylabel('V (N)'); title('Shear, moment and deflection')
subplot(3,1,2); plot(r.x, r.M); grid on; ylabel('M (N m)')
subplot(3,1,3); plot(r.x, 1000*r.deflection); grid on; ylabel('y (mm)'); xlabel('x (m)')

%% 2. Combined stress at a point: Mohr's circle and von Mises
m = mohr(80e6, -40e6, 25e6)
vm = von_mises(80e6, -40e6, 25e6);
fprintf('von Mises %.1f MPa\n', vm/1e6);

%% 3. Vibrations: SDOF free and forced response
p = sdof(2, 4, 800)
t = linspace(0, 2, 1000);
[x, v] = sdof_free(2, 4, 800, 0.01, 0, t);
figure(2); plot(t, 1000*x); grid on; xlabel('t (s)'); ylabel('x (mm)')
title(sprintf('Free response: \\omega_n = %.1f rad/s, \\zeta = %.3f', p.wn, p.zeta))
r_ratio = linspace(0, 3, 300);
figure(3); hold on
for z = [0.05 0.1 0.25 0.5]
    plot(r_ratio, transmissibility(z, r_ratio), 'DisplayName', sprintf('\\zeta = %.2f', z));
end
hold off; grid on; ylim([0 5]); legend; xlabel('r = \omega/\omega_n'); ylabel('TR')
title('Transmissibility')
f = sdof_forced(2, 4, 800, 50, 18);
fprintf('Forced at 18 rad/s: X = %.2f mm, phase %.1f deg\n', 1000*f.X, f.phase);

%% 4. Two-degree-of-freedom system: natural frequencies and mode shapes
M = [2 0; 0 1];
K = [600 -200; -200 200];
md = modes(M, K);
fprintf('Natural frequencies: %.2f and %.2f rad/s\n', md.wn(1), md.wn(2));
disp('Mode shapes (columns):'); disp(md.shapes)
figure(4); bar(md.shapes); grid on; legend('mode 1', 'mode 2'); title('Mode shapes')

%% 5. Machine elements and a four-bar linkage
s = spring_helical(0.004, 0.032, 10, 79.3e9, 100);
fprintf('Spring rate %.0f N/m, shear stress %.1f MPa\n', s.k, s.tau/1e6);
g = gear_pair(20, 60, 0.002, 300, 10)
th2 = 0:5:360; th4 = zeros(size(th2));
for i = 1:numel(th2)
    q = fourbar(2, 7, 9, 6, th2(i));
    th4(i) = q.theta4;
end
figure(5); plot(th2, th4); grid on; xlabel('\theta_2 (deg)'); ylabel('\theta_4 (deg)')
title(sprintf('Four-bar output angle (%s)', q.grashof))

%% 6. Animate the four-bar linkage (joint coordinates r.x, r.y = [O2 A B O4])
figure(6);
for a2 = 0:10:360
    q = fourbar(2, 7, 9, 6, a2);
    plot(q.x, q.y, '-o', 'LineWidth', 2); axis equal; axis([-3 11 -3 9]); grid on
    title(sprintf('\\theta_2 = %d deg', a2)); drawnow
end
