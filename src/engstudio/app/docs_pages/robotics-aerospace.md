# Robotics and Aerospace toolboxes

## Robotics

Angles in radians except `rotx`/`roty`/`rotz`, which take degrees as in MATLAB.

- `rotx(deg)`, `roty(deg)`, `rotz(deg)`: 3-by-3 rotations; `transform(R, p)`: 4-by-4
  homogeneous transform.
- `dh(a, alpha, d, theta)`: standard Denavit-Hartenberg link transform.
- `k = fkine(dh_table, q, prismatic)`: `dh_table` rows `[a alpha d theta_offset]`,
  `prismatic` 0/1 per joint (default all revolute). Fields `T`, `position`, `joints` (one row
  per frame origin, for `plot3`), `euler_zyx` (yaw, pitch, roll in degrees).
- `[x, y, J] = planar_arm(L, q)`: joint coordinates of a planar arm (`plot(x, y, '-o')`) and
  its 2-by-n Jacobian.
- `[q1, q2] = ik_2link(L1, L2, x, y, 'down' | 'up')`: two-link inverse kinematics.
- `[q, qd, qdd] = trajectory(q0, qf, tf, t, 'cubic' | 'quintic' | 'trapezoid', v_max)`.

```
t = linspace(0, 2, 60);
q1 = trajectory(0, pi/2, 2, t, 'quintic'); q2 = trajectory(0, -pi/3, 2, t, 'quintic');
for k = 1:numel(t)
    [x, y] = planar_arm([1 0.7], [q1(k) q2(k)]);
    plot(x, y, '-o'); axis([-2 2 -2 2]); axis equal; drawnow
end
```

## Aerospace

- `[T, a, p, rho] = atmosisa(h)`: International Standard Atmosphere up to 86 km.
- `s = airspeed(V, h)`: `mach`, dynamic pressure `q`, equivalent airspeed `eas`, stagnation
  `T0` and `p0`.
- `[L, D, CD] = lift_drag(V, S, CL, CD0, AR, e, rho)`: parabolic drag polar.
- `stall_speed(W, S, CLmax, rho)`.
- `breguet(kind, LD, W0, W1, c, V, eta)`: `'jet-range'`, `'jet-endurance'`, `'prop-range'`,
  `'prop-endurance'`.
- `rocket_dv(Isp, m0, mf)`: Tsiolkovsky rocket equation.
- `o = orbit(h, mu, R)`: circular speed, escape speed, period (Earth by default).
- `t = hohmann(r1, r2, mu)`: `dv1`, `dv2`, `dv_total`, `transfer_time`.

See `examples/robotics_aero_example.m`.

[Back to index](index.md)
