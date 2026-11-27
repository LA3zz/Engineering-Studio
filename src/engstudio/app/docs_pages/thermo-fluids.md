# Thermodynamics, Fluids and Heat Transfer toolboxes

SI units throughout (Pa, m^3, kg, K, J, W). Air is an ideal gas with R = 287 J/(kg K) and
k = 1.4 unless you pass other values. Results with several values come back as structs.

## Thermodynamics

- `ideal_gas(p, V, m, T, R)`: give three of p, V, m, T and `[]` for the unknown, e.g.
  `p = ideal_gas([], 1, 1.2, 300)`.
- `s = gas_process(kind, p1, V1, V2, m, n, R, cv)`: `'isothermal'`, `'isobaric'`,
  `'isentropic'`, `'polytropic'` (exponent n). Fields `p2`, `V2`, `T2`, work `W`, heat `Q`,
  `dU` (first law: Q = dU + W).
- `c = cycle_efficiency(kind, a, b, k)`: `'carnot'` (TH, TC), `'otto'` (compression ratio),
  `'diesel'` (r, cut-off ratio), `'brayton'` (pressure ratio). Fields `efficiency`, `T_max`, `work_ratio`.
- `cop(kind, TC, TH)`: `'refrigerator'` or `'heat_pump'` (Carnot limit).
- `entropy_change(T1, T2, p1, p2, m, cp, R)` (per kg when m is omitted), `isentropic_temperature(T1, ratio, k)`.

## Fluid mechanics

- `reynolds(V, D, rho, mu)`, `friction_factor(Re, eps_over_D, method)` (`'colebrook'`,
  `'swamee-jain'`, `'haaland'`; 64/Re when laminar).
- `r = pipe_loss(Q, D, L, roughness, K_minor, rho, mu)`: velocity `V`, `Re`, `f`, head loss `hf`,
  pressure drop `dp`, `regime`.
- `bernoulli(p1, V1, z1, V2, z2, rho, head_loss)` gives p2; `hydrostatic(depth, rho, p0)`;
  `pump_power(Q, head, eta, rho)`; `drag_force(Cd, A, V, rho)`;
  `terminal_velocity(m, Cd, A, rho)`; `orifice_flow(Cd, A, dp, rho)`;
  `manning(n, A, P, slope)` (open-channel flow).

## Heat transfer

- Thermal resistances: `conduction_resistance('plane' | 'cylinder' | 'sphere', k, ...)`,
  `convection_resistance(h, A)`; add them in series and divide the temperature difference.
- `[q, h_rad] = radiation(eps, A, Ts, Tsur)`.
- `nusselt(kind, Re, Pr)`: `'dittus-boelter'`, `'laminar-tube'`, `'flat-plate-laminar'`,
  `'flat-plate-turbulent'`, `'churchill-bernstein'`.
- `f = fin(h, k, P, Ac, L, dT)` (corrected length L + Ac/P, dT = T_base - T_inf): `m`, heat rate `q`, `efficiency`.
- `lmtd(Th_in, Th_out, Tc_in, Tc_out, 'counter' | 'parallel')`,
  `effectiveness_ntu(NTU, Cr, 'counter' | 'parallel')`.
- `r = lumped(T0, Tinf, h, A, V, rho, c, k, t)`: temperature history `T`, time constant `tau`,
  Biot number `Bi` and whether the lumped model is `valid` (Bi < 0.1).

```
q = (90 - 20) / (convection_resistance(10, 2) + conduction_resistance('plane', 0.8, 0.2, 2))
r = pipe_loss(0.02, 0.1, 50, 0.045e-3);  fprintf('dp = %.0f Pa\n', r.dp)
```

See `examples/thermo_fluids_example.m`.

[Back to index](index.md)
