# Materials and lab data

## Reading and writing data files

Built-in commands (no toolbox needed) for CSV, TXT, DAT, TSV and Excel files. A file name
without a folder is looked up in the working folder, then next to the running script, so a
script and its data can live together.

- `A = readmatrix('data.csv')`: the numbers as a matrix. Header lines at the top are skipped;
  other text cells become NaN. Options: `'Sheet'` (Excel name or number), `'Delimiter'`.
- `T = readtable('data.xlsx')`: a struct with one field per column, named after the header
  (`Load (kN)` becomes `T.Load__kN_`; see `fieldnames(T)`). Numeric columns are column
  vectors, text columns are cell arrays.
- `writematrix(A, 'out.csv')`, `writetable(T, 'out.xlsx')` (struct of equal-length columns).
- Older names: `csvread(file, r, c)` (zero-based offsets), `csvwrite(file, A)`,
  `xlsread(file, sheet)`, `xlswrite(file, A)`.

## Materials toolbox

- `m = material(name)`: typical `E`, `nu`, `G`, `rho`, `Sy`, `Su`, `alpha`, `k`, `cp` for
  steel, stainless, aluminium, copper, brass, titanium, cast_iron, concrete, wood, glass, abs,
  nylon (handbook averages: check a datasheet for design).
- `r = tensile_test(strain, stress, elastic_limit, offset)`: modulus `E` (least-squares fit of
  the elastic part, by default stresses below 40 % of the peak), 0.2 % offset yield `Sy`,
  `Su`, `strain_at_Su`, `elongation`, `toughness` (area under the curve), `resilience`.
- `thermal_stress(E, alpha, dT, restraint)`: stress in a restrained bar (compressive when
  heated).
- `fatigue_sf(sa, sm, Se, Su, Sy, 'goodman' | 'soderberg' | 'gerber')`: fatigue safety factor.
- `basquin_life(sa, sf, b)`: cycles to failure; `[El, Et] = rule_of_mixtures(Ef, Em, Vf)`.

```
d = readmatrix('tensile_test.csv');          % columns: strain (-), stress (MPa)
r = tensile_test(d(:,1), d(:,2)*1e6);
fprintf('E = %.0f GPa, Sy = %.0f MPa, Su = %.0f MPa\n', r.E/1e9, r.Sy/1e6, r.Su/1e6)
plot(d(:,1), d(:,2)); xlabel('strain'); ylabel('stress (MPa)'); grid on
```

See `examples/lab_data_example.m` and `examples/data/tensile_test.csv`.

[Back to index](index.md)
