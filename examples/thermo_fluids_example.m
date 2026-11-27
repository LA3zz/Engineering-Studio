%% Thermodynamics, fluids and heat transfer - worked examples (Engineering Studio, Phase 8)
clear all; close all; clc

%% 1. Air-standard cycles: Otto vs Diesel efficiency against compression ratio
r = 4:0.5:22;
eta_otto = zeros(size(r)); eta_diesel = zeros(size(r));
for i = 1:numel(r)
    c = cycle_efficiency('otto', r(i));     eta_otto(i) = c.efficiency;
    c = cycle_efficiency('diesel', r(i), 2); eta_diesel(i) = c.efficiency;
end
figure(1); plot(r, 100*eta_otto, r, 100*eta_diesel); grid on
legend('Otto', 'Diesel (cut-off 2)'); xlabel('compression ratio'); ylabel('\eta (%)')
title('Air-standard cycle efficiency')

%% 2. Isentropic compression of 1 kg of air from 100 kPa, 300 K to one eighth of the volume
V1 = ideal_gas(100e3, [], 1, 300);
s = gas_process('isentropic', 100e3, V1, V1/8, 1);
fprintf('Compression: p2 = %.0f kPa, T2 = %.0f K, work done on gas %.1f kJ\n', ...
    s.p2/1e3, s.T2, -s.W/1e3);
fprintf('Carnot COP of a fridge (-5 C / 30 C): %.2f\n', cop('refrigerator', 268, 303));

%% 3. Pipe flow: pressure drop against flow rate in a 50 m steel pipe
Q = linspace(0.001, 0.02, 40); dp = zeros(size(Q));
for i = 1:numel(Q)
    p = pipe_loss(Q(i), 0.08, 50, 0.045e-3);
    dp(i) = p.dp;
end
figure(2); plot(1000*Q, dp/1e3); grid on; xlabel('Q (L/s)'); ylabel('\Delta p (kPa)')
title('Darcy-Weisbach pressure drop')
p = pipe_loss(0.01, 0.08, 50, 0.045e-3);
fprintf('At 10 L/s: V = %.2f m/s, Re = %.0f (%s), f = %.4f, pump power %.0f W\n', ...
    p.V, p.Re, p.regime, p.f, pump_power(0.01, p.hf, 0.7));

%% 4. Heat loss through an insulated steam pipe (resistances in series, per metre)
Rin = convection_resistance(500, 2*pi*0.05*1);
Rpipe = conduction_resistance('cylinder', 45, 0.05, 0.055, 1);
Rins = conduction_resistance('cylinder', 0.04, 0.055, 0.105, 1);
Rout = convection_resistance(10, 2*pi*0.105*1);
q = (180 - 20) / (Rin + Rpipe + Rins + Rout);
fprintf('Heat loss %.1f W per metre of pipe\n', q);

%% 5. Quenching a steel ball: lumped capacitance cooling curve
t = linspace(0, 600, 300);
b = lumped(800, 25, 100, 4*pi*0.01^2, 4/3*pi*0.01^3, 7850, 490, 50, t);
figure(3); plot(t, b.T); grid on; xlabel('t (s)'); ylabel('T (\circC)')
title(sprintf('Lumped cooling: \\tau = %.0f s, Bi = %.3f', b.tau, b.Bi))
