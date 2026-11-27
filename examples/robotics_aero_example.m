%% Robotics and aerospace - worked examples (Engineering Studio, Phase 8)
clear all; close all; clc

%% 1. Two-link arm: reach a target with inverse kinematics, then move smoothly to it
L = [1 0.7];
[q1f, q2f] = ik_2link(L(1), L(2), 1.1, 0.9);
t = linspace(0, 2, 40);
q1 = trajectory(0, q1f, 2, t, 'quintic');
q2 = trajectory(0, q2f, 2, t, 'quintic');
figure(1);
for k = 1:numel(t)
    [x, y] = planar_arm(L, [q1(k) q2(k)]);
    plot(x, y, '-o', 'LineWidth', 2); hold on; plot(1.1, 0.9, 'rx'); hold off
    axis equal; axis([-0.5 2 -0.5 2]); grid on; title(sprintf('t = %.2f s', t(k))); drawnow
end
[x, y, J] = planar_arm(L, [q1f q2f]);
fprintf('End effector at (%.3f, %.3f); det(J) = %.3f\n', x(end), y(end), det(J));

%% 2. Forward kinematics of a 3-joint arm from a DH table
dhtab = [0 pi/2 0.4 0; 0.5 0 0 0; 0.4 0 0 0];
k = fkine(dhtab, [pi/6 pi/4 -pi/3]);
fprintf('Tool position: [%.3f %.3f %.3f] m\n', k.position);
figure(2); plot3(k.joints(:,1), k.joints(:,2), k.joints(:,3), '-o'); grid on
title('3-DOF arm (DH)')

%% 3. Standard atmosphere
h = linspace(0, 30e3, 200);
[T, a, p, rho] = atmosisa(h);
figure(3);
subplot(1,2,1); plot(T - 273.15, h/1e3); grid on; xlabel('T (\circC)'); ylabel('h (km)')
subplot(1,2,2); plot(rho, h/1e3); grid on; xlabel('\rho (kg/m^3)')

%% 4. Aircraft performance
W = 1100*9.81; S = 16.2;
fprintf('Stall speed: %.1f m/s\n', stall_speed(W, S, 1.6));
s = airspeed(250, 11000);
fprintf('250 m/s at 11 km: Mach %.2f, q = %.0f Pa\n', s.mach, s.q);
R = breguet('jet-range', 17, 75e3, 60e3, 1.7e-4, 230);
fprintf('Breguet range: %.0f km\n', R/1e3);

%% 5. Spaceflight: rocket stage and a LEO -> GEO transfer
fprintf('Stage delta-v: %.0f m/s\n', rocket_dv(320, 50e3, 15e3));
o = orbit(400e3)
hm = hohmann(6771e3, 42164e3);
fprintf('Hohmann LEO->GEO: %.0f m/s total, %.1f h\n', hm.dv_total, hm.transfer_time/3600);
