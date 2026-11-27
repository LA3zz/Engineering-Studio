# Control systems and PID

Linear systems are values like numbers: create them, combine them with operators, and pass
them to analysis and plot commands. Their class is `tf`, `zpk` or `ss`.

## Creating systems

- Transfer function: `G = tf(1, [1 2 1])`, or with `s = tf('s'); G = 1/(s^2 + 2*s + 1)`.
- Zero-pole-gain: `Z = zpk([-3], [-1 -2], 5)`; state space: `S = ss(A, B, C, D)`.
- Discrete: `tf(num, den, Ts)` or `Gd = c2d(G, 0.1)` (methods 'zoh', 'foh', 'tustin',
  'matched', 'impulse').
- Convert: `tf(Z)`, `zpk(G)`, `ss(G)`; read back: `[num, den] = tfdata(G)`,
  `[z, p, k] = zpkdata(G)`, `[A, B, C, D] = ssdata(G)`.

## Combining

`G1*G2` (series), `G1 + G2` (parallel), `k*G`, `G/k`, `G^n`, `feedback(G, H)`
(negative feedback; `feedback(G, H, +1)` for positive), `series`, `parallel`, `minreal`.

## Analysis

`pole`, `zero`, `dcgain`, `damp`, `isstable`, `order`, `isdt`,
`info = stepinfo(T)` (RiseTime, SettlingTime, Overshoot, Peak, PeakTime, ...),
`[Gm, Pm, Wcg, Wcp] = margin(L)`.

## Plots

`step`, `impulse`, `initial(sys, x0)`, `lsim(sys, u, t)`, `bode`, `margin`, `nyquist`,
`rlocus`, `pzmap`. Several systems may be drawn together, each followed by a line style:
`step(G, 'b', feedback(G, 1), 'r--')`. With output arguments the commands return data instead
of plotting: `[y, t] = step(G)`, `[mag, phase, w] = bode(G)`.

## PID controllers

- `C = pid(Kp, Ki, Kd, Tf)` (parallel form) or `pidstd(Kp, Ti, Td, N)` (standard form);
  the result is a transfer function.
- `[C, info] = pidtune(G, 'PID')` designs a P, PI, PD or PID controller for a 60 degree phase
  margin; `pidtune(G, 'PI', wc)` fixes the crossover frequency `wc` (rad/s).

## Example

```
s = tf('s');
G = 1/(s*(s + 1)*(s + 5));      % plant
[C, info] = pidtune(G, 'PID');  % controller
T = feedback(C*G, 1);           % closed loop
step(T); stepinfo(T)
figure; margin(C*G)
```

[Back to index](index.md)
