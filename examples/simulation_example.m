%% Simulation from scripts (Engineering Studio, Phase 7)
% Runs the example block diagrams in examples/models. Open them in the editor with
% open_system('models/mass_spring_damper.esmodel') or Simulation > Open Model.
clear all; close all; clc
here = 'models';   % relative to this script's folder (sim also looks there)

%% 1. Mass-spring-damper: compare the simulation with the exact solution
out = sim([here '/mass_spring_damper.esmodel']);
m = 1; c = 0.4; k = 4; F = 1;
p = sdof(m, c, k);                                   % Mechanical toolbox
t = out.tout;
x_exact = zeros(size(t));
idx = t >= 1;                                        % force steps up at t = 1 s
tau = t(idx) - 1;
x_exact(idx) = F/k*(1 - exp(-p.zeta*p.wn*tau).*(cos(p.wd*tau) + p.zeta*p.wn/p.wd*sin(p.wd*tau)));
fprintf('Mass-spring-damper: max error vs exact = %.2e m\n', max(abs(out.x - x_exact)));
figure(1); plot(t, out.x, 'b', t, x_exact, 'r--'); grid on
legend('simulation', 'exact'); xlabel('t (s)'); ylabel('x (m)'); title('Mass-spring-damper')

%% 2. PID position loop: plots its Scope and stores out in the workspace
sim([here '/pid_position_loop.esmodel'], 'StopTime', 2)
fprintf('PID loop: final angle %.4f rad\n', out.theta(end));

%% 3. Sampled-data control with a different solver
out3 = sim([here '/sampled_control.esmodel'], 'Solver', 'rk4', 'FixedStep', 0.01);
fprintf('Sampled control with rk4: %d output points up to t = %g s\n', numel(out3.tout), out3.tout(end));
