# Mechanical Engineering toolbox

Functions for mechanics of materials, vibrations and machine elements. Use SI units (m, N, Pa,
kg, s). Results with several values come back as a struct: `p = sdof(2, 4, 800); p.wn`.

## Sections and stress

- `section_rect(b, h)`, `section_circle(d)`, `section_tube(do, di)`,
  `section_ibeam(bf, tf, h, tw)`: area `A`, `Ix`, `Iy`, `J`, section moduli `Sx`, `Sy`, radii of
  gyration `rx`, `ry`, extreme-fibre distance `c`.
- `stress_axial(F, A)`, `stress_bending(M, c, I)`, `stress_torsion(T, r, J)`.
- `mohr(sx, sy, txy)`: principal stresses `s1`, `s2`, `tau_max`, angle `theta_p` (degrees).
- `von_mises(sx, sy, txy, sz, tyz, tzx)` (omit the z terms for plane stress),
  `safety_factor(stress, strength)`, `buckling_euler(E, I, L, K)` (K = 1, 0.5, 0.699, 2).

## Beams

`r = beam(L, E, I, 'simply' | 'cantilever', P, a, w)`: point loads `P` at positions `a`
(downward positive) and a uniform load `w`. Fields: `x`, shear `V`, moment `M`, `slope`,
`deflection` (upward positive), `reactions`, `max_deflection`, `max_moment` and where they occur.

```
r = beam(2, 200e9, 8e-6, 'simply', [1000 500], [0.5 1.5], 200);
subplot(2,1,1); plot(r.x, r.M); ylabel('M (N m)'); grid on
subplot(2,1,2); plot(r.x, r.deflection*1000); ylabel('y (mm)'); xlabel('x (m)'); grid on
```

## Vibrations

- `p = sdof(m, c, k)`: `wn`, `fn`, `Tn`, `zeta`, `wd`, `fd`, `ccr`, `regime`.
- `[x, v] = sdof_free(m, c, k, x0, v0, t)`: exact free response (any damping).
- `f = sdof_forced(m, c, k, F0, w)`: amplitude `X`, `phase` (deg), `r`, magnification `MF`,
  transmissibility `TR`.
- `transmissibility(zeta, r)` (r may be a vector), `log_decrement(x1, xn, n)` (`delta`, `zeta`).
- `md = modes(M, K)`: natural frequencies `wn`/`fn` and mode shapes (`shapes` scaled to 1,
  `shapes_mass` mass-normalised); free-free systems give a 0 rad/s rigid-body mode. Works for
  torsional systems with inertia and stiffness matrices.

## Machine elements and mechanisms

- `spring_helical(d, D, n, G, F)`: rate `k`, index `C`, Wahl factor `Kw`, shear stress `tau`.
- `gear_pair(N1, N2, module, w1, T1)`, `shaft_power(T, rpm)`, `shaft_diameter(T, tau_allow)`.
- `fourbar(a, b, c, d, theta2, omega2, 'open' | 'crossed')`: coupler and output angles and
  angular velocities, the Grashof type and joint coordinates `x`, `y` (`[O2 A B O4]`), so
  `plot(r.x, r.y, '-o')` draws the linkage; loop over `theta2` with `drawnow` to animate it.

See `examples/mechanical_example.m`.

[Back to index](index.md)
