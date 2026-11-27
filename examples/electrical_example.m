%% Electrical and electronics - worked examples (Engineering Studio, Phase 8)
clear all; close all; clc

%% 1. RC charging and RL current build-up
t = linspace(0, 5e-3, 400);
[vC, iC] = rc_step(1e3, 1e-6, 5, t);
[iL, vL] = rl_step(10, 10e-3, 12, t);
figure(1);
subplot(2,1,1); plot(1000*t, vC); grid on; ylabel('v_C (V)'); title('RC step (\tau = 1 ms)')
subplot(2,1,2); plot(1000*t, iL); grid on; ylabel('i_L (A)'); xlabel('t (ms)')

%% 2. Series RLC: damping and resonance
s = rlc(20, 10e-3, 1e-6)
fprintf('f0 = %.0f Hz, Q = %.2f, %s\n', s.f0, s.Q, s.response);

%% 3. AC load power and power-factor correction
Z = impedance('R', 30, 50) + impedance('L', 0.127, 50);
p = ac_power(230, Z);
fprintf('P = %.0f W, Q = %.0f var, pf = %.3f\n', p.P, p.Q, p.pf);
C = p.Q / (2*pi*50*230^2);                       % capacitor that cancels the reactive power
p2 = ac_power(230, 1/(1/Z + 1/impedance('C', C, 50)));
fprintf('With %.1f uF in parallel: pf = %.3f\n', C*1e6, p2.pf);
[P3, Q3, S3] = three_phase_power(400, 16, 0.85);
fprintf('Three-phase 400 V, 16 A, pf 0.85: P = %.1f kW\n', P3/1e3);

%% 4. Electronics: op-amp gain, RC filter Bode magnitude, diode curve, 555 timer
fprintf('Inverting amplifier gain: %.1f\n', opamp_gain('inverting', 47e3, 4.7e3));
f = logspace(1, 5, 200);
[fc, H] = rc_filter(1e3, 100e-9, 'lowpass', f);
figure(2); semilogx(f, 20*log10(abs(H))); grid on; xline(fc, '--');
xlabel('f (Hz)'); ylabel('|H| (dB)'); title(sprintf('RC low-pass, f_c = %.0f Hz', fc))
V = linspace(0, 0.75, 200);
figure(3); plot(V, 1000*diode_current(V)); grid on; xlabel('V (V)'); ylabel('I (mA)')
title('Shockley diode')
tm = timer555(1e3, 10e3, 10e-6);
fprintf('555 astable: f = %.2f Hz, duty %.0f %%\n', tm.f, 100*tm.duty);
