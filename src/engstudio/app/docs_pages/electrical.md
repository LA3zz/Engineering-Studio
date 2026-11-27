# Electrical and Electronics toolbox

SI units (ohm, F, H, V, A, W, Hz). Complex numbers are phasors: `abs(Z)`, `angle(Z)`.

## Circuits

- `resistors(R, 'series' | 'parallel')`: equivalent resistance of a vector of resistors.
- `voltage_divider(Vin, R1, R2, Rload)`: output across R2, optionally loaded.
- `s = rlc(R, L, C, 'series' | 'parallel')`: `wn`, `zeta`, neper frequency `alpha`,
  resonance `f0` (Hz), quality factor `Q`, `bandwidth` (Hz), `response` type.
- `[vC, i] = rc_step(R, C, V, t, V0)`: capacitor charging from V0 towards V.
- `[i, vL] = rl_step(R, L, V, t)`: current build-up after a voltage step.

## AC power

- `impedance('R' | 'L' | 'C', value, f)`: complex impedance at frequency f.
- `p = ac_power(V, Z)`: real `P`, reactive `Q`, apparent `S`, power factor `pf`, current
  phasor `current` for an rms voltage V across Z.
- `[P, Q, S] = three_phase_power(VL, IL, pf)`: balanced three-phase load from line values.

## Electronics

- `opamp_gain('inverting' | 'noninverting' | 'follower' | 'differential', Rf, Rin)`.
- `[fc, H] = rc_filter(R, C, 'lowpass' | 'highpass', f)`: cut-off and complex response.
- `diode_current(V, Is, n, T)`: Shockley equation.
- `t = timer555(R1, R2, C)`: astable frequency `f`, `duty`, `t_high`, `t_low`.

```
f = logspace(1, 5, 200);
[fc, H] = rc_filter(1e3, 100e-9, 'lowpass', f);
semilogx(f, 20*log10(abs(H))); xline(fc, '--'); grid on
xlabel('f (Hz)'); ylabel('|H| (dB)')
```

See `examples/electrical_example.m`.

[Back to index](index.md)
