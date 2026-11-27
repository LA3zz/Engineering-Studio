# Structures and FEA (2-D)

Linear-elastic finite element analysis in the plane. Nodes and elements are numbered from 1,
as in MATLAB. SI units (m, N, Pa).

## Trusses

`r = truss2d(nodes, elements, E, A, supports, loads)`

- `nodes`: one `[x y]` row per node; `elements`: one `[node1 node2]` row per member.
- `E`, `A`: one value, or one per member.
- `supports`: `[node fixX fixY]` rows (1 = fixed); `loads`: `[node Fx Fy]` rows.
- Fields: displacements `u` (`[ux uy]` per node), member forces `N` (tension positive),
  `stress`, `reactions`, `length`. An unstable structure gives a "mechanism" error.

## Frames

`r = frame2d(nodes, elements, E, A, I, supports, loads, w)`

- `supports`: `[node fixX fixY fixRotation]`; `loads`: `[node Fx Fy M]`.
- `w`: uniform load on each member along its local y axis (90 degrees anticlockwise from
  node1 to node2), so a left-to-right beam carrying gravity load has `w < 0`.
- Fields: `u` (`[ux uy rotation]` per node), axial force `N`, shear `V` and moment `M` at
  the `[start end]` of each member (sagging positive), `reactions` (`[Rx Ry Mz]`), `length`.

## Plates (plane stress)

`r = plate2d(Lx, Ly, t, E, nu, nx, ny, support, load_edge, traction, hole_radius)`

- Rectangular plate meshed with nx-by-ny four-node elements.
- `support`: `'left'` or `'bottom'` clamps that edge; `'left-roller'`/`'bottom-roller'`
  only stops the normal direction (plus one corner).
- `traction`: `[tx ty]` in Pa on `load_edge` (`'right'`, `'top'`, `'left'`, `'bottom'`).
- `hole_radius`: optional central hole (stress concentration studies).
- Fields: node grids `X`, `Y`, displacements `ux`, `uy`, stresses `sx`, `sy`, `txy`,
  `von_mises` (NaN inside the hole), `max_von_mises`, `max_displacement`.

```
r = plate2d(0.4, 0.2, 0.005, 200e9, 0.3, 60, 30, 'left-roller', 'right', [10e6 0], 0.03);
contourf(r.X, r.Y, r.von_mises/1e6, 20); colorbar; axis equal
title(sprintf('von Mises (MPa), Kt = %.2f', r.max_von_mises/10e6))
```

Meshes are kept small (at most 200 by 200 elements) so a solve takes well under a second.
For beams with point loads and standard supports, `beam` in the
[Mechanical Engineering toolbox](mechanical.md) gives the full deflection curve directly.
See `examples/fea_example.m`.

[Back to index](index.md)
