# Math engine API (E1-E12)

Python API of `engstudio.engine`. These functions are used by the Python code and, later, by
the scripting language; they are not yet callable from the Command Window. Back to the
[documentation index](index.md).

## Conventions

- Functions are pure: inputs are validated copies, never modified. No global state.
- Everything is in SI units. Conversions are explicit (`core.units.convert`).
- Results with metadata are frozen dataclasses; simple results are plain arrays or numbers.
- Failure raises a typed error from `core.errors`: `ValidationError` (bad value or type),
  `DimensionError` (shape mismatch), `SingularMatrixError` (has `.rcond`), `ConvergenceError`
  (has `.iterations`, `.last_estimate`), `NotSupportedError`.
- Degraded but valid results (for example `rcond < 1e-12`) are returned with a warning
  `Diagnostic` in `result.diagnostics`.
- Tolerances (`rtol`, `atol`) are explicit keyword arguments with documented defaults.
- Differences from MATLAB are documented per function (for example `std` uses `ddof=1`).

## validation

`as_matrix(a, name, *, allow_complex, square, allow_empty)`,
`as_vector(a, name, *, allow_complex, allow_empty, length)`, `singular_error(message, rcond)`.
NaN/Inf, empty, ragged and non-numeric input raise `ValidationError`.

## linalg (E1)

`solve(a, b) -> SolveResult(x, residual_norm, rcond, method, diagnostics)`,
`inv(a) -> InvResult(value, rcond, diagnostics)`, `det`, `trace`, `matmul`, `transpose`,
`ctranspose`, `dot` (conjugates the first argument), `cross`, `norm(x, kind=2)`,
`rank(a, tol=None)`, `cond(a, p=2)`, `rcond(a)`.
`rcond < eps` raises `SingularMatrixError`; `rcond < 1e-12` adds an ILL_CONDITIONED warning.

## decomp (E2)

`lu(a) -> LuResult(P, L, U)`, `qr(a, mode="full") -> QrResult(Q, R, mode)`,
`svd(a, full=False) -> SvdResult(U, s, V)`,
`cholesky(a, lower=False, tol=1e-12) -> CholResult(factor, lower)`,
`eig(a)` and `eigh(a, tol=1e-12)` -> `EigResult(values, vectors, residual, vector_rcond,
diagnostics)`.

## calculus (E3)

`derivative(f, x, *, order=1, h=None, method="central")`, `gradient(f, x)`, `jacobian(f, x)`,
`derivative_data(x, y)`, `quad(f, a, b, *, rtol, atol, limit)`,
`dblquad(f, x0, x1, y0, y1, *, rtol, atol)` -> `IntegrateResult(value, error_estimate, nfev,
converged, diagnostics)`; `trapz`, `simpson`, `cumtrapz` take `(y, x=None, dx=1.0)`.

## roots (E4)

`bisect`, `brentq` (bracketing, `f, a, b`), `newton(f, x0, *, fprime=None)`,
`secant(f, x0, x1)`, `fsolve(f, x0, *, jac=None)`, `polyroots(coeffs)`.
Solvers return `RootResult(root, converged, iterations, residual, diagnostics, method, nfev)`.

## interp (E5)

`interp1(x, y, xq, *, method="linear", extrap="error")`,
`interp2(x, y, z, xq, yq, *, method="linear", extrap="error")`.
Queries outside the data raise an error unless `extrap` allows them.

## regression (E6)

`linfit(A, y, *, weights=None)`, `polyfit(x, y, deg, *, weights=None)`, `polyval(p, x)`,
`fit_curve(f, x, y, p0, *, sigma=None, absolute_sigma=False, bounds=None, maxfev=2000)`,
`confidence_intervals(result, level=0.95)`.
Fits return `FitResult(params, covariance, residuals, r_squared, diagnostics, stderr, dof,
method, nfev)`.

## optimize (E7)

`minimize_scalar(f, a, b, *, xtol=1e-10, maxiter=500)`,
`minimize(f, x0, *, jac, bounds, constraints, method, tol=1e-8, maxiter=1000)`,
`linprog(c, A_ub, b_ub, A_eq, b_eq, bounds)`.
Results: `MinimizeResult(x, fun, converged, iterations, nfev, diagnostics, method)`.

## stats (E8)

`mean`, `median`, `var`, `std` (`ddof=1`), `sem`, `rms`, `skewness`, `kurtosis`, `iqr`,
`quantile(x, q)`, `zscore`, `cov(x, y)`, `pearsonr(x, y) -> CorrResult(r, p_value, n)`,
`summary(x) -> Summary(n, mean, std, sem, min, q1, median, q3, max)`,
`confidence_interval_mean(x, level=0.95)` returns `(mean, low, high)`,
`ttest_1samp`, `ttest_ind` (`equal_var=False`), `ttest_paired` ->
`TestResult(statistic, p_value, dof, diagnostics, method)`, and
`histogram(x, bins=10, *, range_=None)` returns `(counts, edges)`.

## ode (E9)

`solve_ode(f, t_span, y0, *, method="RK45", rtol=1e-6, atol=1e-9, t_eval, events, jac,
max_step, first_step, max_nfev=200000) -> OdeResult`.
Methods: RK45, RK23, DOP853, Radau, BDF, LSODA. `f(t, y)` returns dy/dt. `OdeResult.y` has
shape `(len(t), n_states)`; `status` 0 = reached the end, 1 = stopped by a terminal event.
`ConvergenceError` is raised on step-size failure, non-finite derivatives or `max_nfev`.

## transforms (E10)

`fft`, `ifft`, `rfft`, `irfft`, `fftfreq`, `rfftfreq`, `window(name, n, *, periodic=True)`,
`amplitude_spectrum(x, fs, *, window="rect", n=None)`,
`psd(x, fs, *, window="hann", detrend=True)` (units x^2/Hz) ->
`SpectrumResult(freq, values, kind, window, fs, diagnostics)`,
`convolve(a, b, mode="full")`, `butter_filter(x, fs, cutoff, *, btype="low", order=4,
zero_phase=True)`. The forward FFT is unnormalised and the inverse divides by N. Uniform
sampling is assumed and cannot be checked.

## symbolic (E11)

`SymExpr`, `parse`, `simplify`, `expand`, `factor`, `subs`, `equivalent`, `to_numeric`,
`lambdify`, `diff(e, var, order=1)`, `integrate(e, var, a=None, b=None)`, `limit`, `series`,
`solve`, `solve_system`, `laplace(e, t, s)`, `inverse_laplace(e, s, t)` (valid for t > 0).
Text input uses `^` for powers and needs explicit multiplication. Results that SymPy cannot
express in closed form raise `NotSupportedError` rather than returning an unevaluated
expression. `solve_system` can miss solutions of nonlinear systems, and `equivalent` returning
False means "not shown equal".

## uncertainty (E12)

`propagate(f, x, ux, *, method="linear", corr=None, coverage=0.95, k=None, n=100000, seed=0,
vectorized=False) -> UncertaintyResult`. `"linear"` is the GUM first-order law;
`"montecarlo"` samples normal inputs (seeded by default for reproducibility).
`contributions[i] = |g_i| ux[i]` are not additive when inputs are correlated.
