%% Control systems and PID - worked example (Engineering Studio, Phase 6)
% Plant: DC motor position, G(s) = K / (s (J s + b)) with J = 0.01, b = 0.1, K = 0.5
clear all; close all; clc

J = 0.01; b = 0.1; K = 0.5;
s = tf('s');
G = K/(s*(J*s + b))

%% Open-loop analysis
fprintf('Open-loop poles:\n'); disp(pole(G))
damp(G)
figure(1); bode(G); title('Open-loop Bode diagram')

%% PID design for a 60 degree phase margin
[C, info] = pidtune(G, 'PID')
fprintf('Kp = %.3f, Ki = %.3f, Kd = %.4f, crossover %.2f rad/s, PM %.1f deg\n', ...
    info.Kp, info.Ki, info.Kd, info.CrossoverFrequency, info.PhaseMargin);

L = C*G;          % loop
T = feedback(L, 1) % closed loop
fprintf('Closed loop stable: %d\n', isstable(T));
S = stepinfo(T)

%% Responses
figure(2); step(feedback(G, 1), 'b--', T, 'r'); legend('P only (K = 1)', 'PID'); grid on
figure(3); margin(L)
figure(4); rlocus(G)
figure(5); nyquist(L)
figure(6); pzmap(T)

%% Disturbance: input sine wave through the closed loop
t = 0:0.005:3;
u = sin(4*t);
figure(7); lsim(T, u, t)

%% Digital implementation (zero-order hold, 10 ms)
Td = c2d(T, 0.01);
figure(8); step(Td); title('Discrete closed loop (Ts = 0.01 s)')
fprintf('Final value of the step response: %.4f\n', dcgain(T));
