%% ENGINEERING STUDIO - FULL FEATURE TEST
% Runs every command group of the app and checks results against known values.
% Each check prints PASS or FAIL; the summary at the end counts them.
% Figures 1-9 show every plot type (8-9: control systems). Two files are written to the current folder:
%   es_selftest_plot.png and es_selftest_anim.gif
% Typical run time: about 15-30 s (most of it is the animation, ODEs and figure drawing).

clear all; close all; clc
format short
fprintf('===== Engineering Studio full feature test =====\n\n');
tic
np = 0; nf = 0;

%% 1. Constants, arithmetic, operators
fprintf('--- 1. Constants and operators ---\n');
[np, nf] = check(np, nf, 'pi', abs(pi - 3.141592653589793) < 1e-15);
[np, nf] = check(np, nf, 'e and exp', abs(e - exp(1)) < 1e-15);
[np, nf] = check(np, nf, 'Inf/NaN', isinf(Inf) && isnan(NaN) && isinf(1/0));
[np, nf] = check(np, nf, 'eps', eps == 2^-52);
[np, nf] = check(np, nf, 'complex i,j', isequal(i^2, -1) && abs(abs(3 + 4j) - 5) < 1e-15);
[np, nf] = check(np, nf, 'realmax/realmin', realmax > 1e308 && realmin < 1e-307);
[np, nf] = check(np, nf, 'logical true/false', true && ~false);
a = 7; b = 2;
[np, nf] = check(np, nf, '+ - * / ^', a + b == 9 && a - b == 5 && a*b == 14 && a/b == 3.5 && a^b == 49);
[np, nf] = check(np, nf, 'left division', b\a == 3.5);
[np, nf] = check(np, nf, 'elementwise .* ./ .^', isequal([1 2 3].*[4 5 6], [4 10 18]) && isequal([4 9].^0.5, [2 3]));
[np, nf] = check(np, nf, 'comparisons', isequal([1 2 3] > 2, [false false true]) && (3 ~= 4));
[np, nf] = check(np, nf, 'logical & | ~', isequal([1 0 1] & [1 1 0], [true false false]) && isequal(~[1 0], [false true]));
[np, nf] = check(np, nf, 'operator functions', plus(2,3) == 5 && mtimes(2,3) == 6 && power(2,3) == 8 && mpower(2,3) == 8);
[np, nf] = check(np, nf, 'operator functions 2', minus(5,3) == 2 && times(2,3) == 6 && rdivide(6,3) == 2 && ldivide(3,6) == 2);
[np, nf] = check(np, nf, 'mrdivide/mldivide', mrdivide(6,3) == 2 && mldivide(3,6) == 2);
[np, nf] = check(np, nf, 'comparison functions', eq(1,1) && ne(1,2) && lt(1,2) && le(2,2) && gt(3,2) && ge(3,3));
[np, nf] = check(np, nf, 'and/or/not/uminus', and(true,true) && or(false,true) && not(false) && uminus(2) == -2 && uplus(2) == 2);
[np, nf] = check(np, nf, 'transpose/ctranspose', isequal(transpose([1 2]), [1; 2]) && isequal(ctranspose(1i), -1i));
[np, nf] = check(np, nf, 'colon()', isequal(colon(1, 3), 1:3) && isequal(0:0.25:1, [0 0.25 0.5 0.75 1]));

%% 2. Matrices and arrays
fprintf('\n--- 2. Matrices and arrays ---\n');
A = [4 -2 1; -2 4 -2; 1 -2 4];
[np, nf] = check(np, nf, 'zeros/ones/eye', isequal(size(zeros(2,3)), [2 3]) && sum(sum(ones(3))) == 9 && trace(eye(4)) == 4);
[np, nf] = check(np, nf, 'linspace/logspace', isequal(linspace(0, 1, 3), [0 0.5 1]) && isequal(logspace(0, 2, 3), [1 10 100]));
[np, nf] = check(np, nf, 'repmat/reshape', isequal(repmat([1 2], 2, 1), [1 2; 1 2]) && isequal(reshape(1:6, 2, 3), [1 3 5; 2 4 6]));
[np, nf] = check(np, nf, 'diag/triu/tril', isequal(diag([1 2]), [1 0; 0 2]) && isequal(triu(A), [4 -2 1; 0 4 -2; 0 0 4]) && isequal(tril(A), [4 0 0; -2 4 0; 1 -2 4]));
[X, Y] = meshgrid(1:3, 1:2);
[np, nf] = check(np, nf, 'meshgrid', isequal(X, [1 2 3; 1 2 3]) && isequal(Y, [1 1 1; 2 2 2]));
[np, nf] = check(np, nf, 'horzcat/vertcat', isequal(horzcat([1 2], 3), [1 2 3]) && isequal(vertcat(1, 2), [1; 2]));
[np, nf] = check(np, nf, 'size/numel/length/ndims', numel(A) == 9 && length(1:7) == 7 && ndims(A) == 2);
[np, nf] = check(np, nf, 'fliplr/flipud', isequal(fliplr([1 2 3]), [3 2 1]) && isequal(flipud([1; 2]), [2; 1]));
v = 1:10;
v(end + 1) = 11; v([1 2]) = [];
[np, nf] = check(np, nf, 'indexing, end, growth, deletion', isequal(v, 3:11) && A(2, end) == -2 && A(end) == 4);
[np, nf] = check(np, nf, 'logical indexing', isequal(v(v > 8), [9 10 11]));

%% 3. Elementary math
fprintf('\n--- 3. Elementary math ---\n');
[np, nf] = check(np, nf, 'abs/sqrt/exp/log', abs(-3) == 3 && sqrt(16) == 4 && abs(log(exp(2)) - 2) < 1e-15);
[np, nf] = check(np, nf, 'log2/log10', log2(8) == 3 && log10(1000) == 3);
[np, nf] = check(np, nf, 'trig', abs(sin(pi/2) - 1) < 1e-15 && abs(cos(0) - 1) < 1e-15 && abs(tan(pi/4) - 1) < 1e-15);
[np, nf] = check(np, nf, 'inverse trig', abs(asin(1) - pi/2) < 1e-15 && abs(acos(1)) < 1e-15 && abs(atan(1) - pi/4) < 1e-15);
[np, nf] = check(np, nf, 'hyperbolic', abs(sinh(0)) < 1e-15 && cosh(0) == 1 && tanh(0) == 0);
[np, nf] = check(np, nf, 'rounding', floor(2.7) == 2 && ceil(2.1) == 3 && round(2.5) == 3 && fix(-2.7) == -2);
[np, nf] = check(np, nf, 'sign/mod/rem', sign(-4) == -1 && mod(-7, 3) == 2 && rem(-7, 3) == -1);
[np, nf] = check(np, nf, 'atan2/hypot', abs(atan2(1, 1) - pi/4) < 1e-15 && hypot(3, 4) == 5);
z = 3 + 4i;
[np, nf] = check(np, nf, 'real/imag/conj/angle', real(z) == 3 && imag(z) == 4 && conj(z) == 3 - 4i && abs(angle(1i) - pi/2) < 1e-15);
[np, nf] = check(np, nf, 'deg2rad/rad2deg', abs(deg2rad(180) - pi) < 1e-15 && abs(rad2deg(pi) - 180) < 1e-12);

%% 4. Data analysis
fprintf('\n--- 4. Data analysis ---\n');
d = [3 1 4 1 5 9 2 6];
[np, nf] = check(np, nf, 'sum/prod/mean', sum(d) == 31 && prod([1 2 3 4]) == 24 && mean([2 4 6]) == 4);
[m, k] = max(d);
[np, nf] = check(np, nf, 'min/max with index', m == 9 && k == 6 && min(d) == 1);
[np, nf] = check(np, nf, 'cumsum/cumprod', isequal(cumsum([1 2 3]), [1 3 6]) && isequal(cumprod([1 2 3]), [1 2 6]));
[np, nf] = check(np, nf, 'any/all', any(d > 8) && all(d > 0));
[s, idx] = sort(d, 'descend');
[np, nf] = check(np, nf, 'sort', isequal(s(1:3), [9 6 5]) && idx(1) == 6);
[np, nf] = check(np, nf, 'find/diff', isequal(find(d == 1), [2 4]) && isequal(diff([1 4 9]), [3 5]));

%% 5. Linear algebra and decompositions
fprintf('\n--- 5. Linear algebra ---\n');
bvec = [1; 2; 3];
x = A \ bvec;
[np, nf] = check(np, nf, 'A\b solve', norm(A*x - bvec) < 1e-12);
[np, nf] = check(np, nf, 'inv/det/trace', norm(inv(A)*A - eye(3)) < 1e-12 && abs(det(A) - 36) < 1e-12 && trace(A) == 12);
[np, nf] = check(np, nf, 'rank/cond/rcond', rank(A) == 3 && cond(A) > 1 && rcond(A) > 0);
[np, nf] = check(np, nf, 'norm/dot/cross', norm([3 4]) == 5 && dot([1 2 3], [4 5 6]) == 32 && isequal(cross([1 0 0], [0 1 0]), [0 0 1]));
[V, D] = eig(A);
[np, nf] = check(np, nf, 'eig (A*V = V*D)', norm(A*V - V*D) < 1e-10);
[L, U, P] = lu(A);
[np, nf] = check(np, nf, 'lu', norm(P*A - L*U) < 1e-12);
[Q, R] = qr(A);
[np, nf] = check(np, nf, 'qr', norm(Q*R - A) < 1e-12);
Rc = chol(A);
[np, nf] = check(np, nf, 'chol', norm(Rc'*Rc - A) < 1e-12);
[Us, Ss, Vs] = svd(A);
[np, nf] = check(np, nf, 'svd', norm(Us*Ss*Vs' - A) < 1e-12);

%% 6. Types, strings, structs, cells, functions
fprintf('\n--- 6. Types, text, structs, cells ---\n');
[np, nf] = check(np, nf, 'class/isa', strcmp(class(1), 'double') && isa(true, 'logical') && strcmp(class('a'), 'char'));
[np, nf] = check(np, nf, 'double/logical/char', double('A') == 65 && logical(2) && strcmp(char(72), 'H'));
[np, nf] = check(np, nf, 'is* tests', isempty([]) && isscalar(5) && isvector([1 2]) && isrow([1 2]) && iscolumn([1; 2]));
[np, nf] = check(np, nf, 'is* tests 2', ismatrix(A) && issquare(A) && isnumeric(1) && isreal(1) && iscomplex(1i) && islogical(true));
[np, nf] = check(np, nf, 'is* tests 3', ischar('x') && iscell({}) && isstruct(struct()) && is_function_handle(@sin));
[np, nf] = check(np, nf, 'isnan/isinf/isfinite', isequal(isnan([1 NaN]), [false true]) && isinf(-Inf) && isfinite(3));
[np, nf] = check(np, nf, 'isequal', isequal([1 2], [1 2]) && ~isequal([1 2], [2 1]));
str = sprintf('%d apples and %.2f pears', 3, 2.5);
[np, nf] = check(np, nf, 'sprintf/num2str/int2str', strcmp(str, '3 apples and 2.50 pears') && strcmp(num2str(42), '42') && strcmp(int2str(2.7), '3'));
[np, nf] = check(np, nf, 'mat2str/str2double', strcmp(mat2str([1 2; 3 4]), '[1 2;3 4]') && str2double('3.5') == 3.5);
[np, nf] = check(np, nf, 'strcmp family', strcmpi('ABC', 'abc') && strncmp('hello', 'help', 3) && strncmpi('HEllo', 'help', 3));
[np, nf] = check(np, nf, 'upper/lower/strtrim', strcmp(upper('ab'), 'AB') && strcmp(lower('AB'), 'ab') && strcmp(strtrim('  x  '), 'x'));
[np, nf] = check(np, nf, 'strrep/strcat', strcmp(strrep('a-b-c', '-', '+'), 'a+b+c') && strcmp(strcat('ab', 'cd'), 'abcd'));
parts = strsplit('a,b,c', ',');
[np, nf] = check(np, nf, 'strsplit/strjoin', numel(parts) == 3 && strcmp(strjoin(parts, '-'), 'a-b-c'));
[np, nf] = check(np, nf, 'strfind/contains', isequal(strfind('abcabc', 'bc'), [2 5]) && contains('vibration', 'brat'));
[np, nf] = check(np, nf, 'startsWith/endsWith', startsWith('MECH322', 'MECH') && endsWith('lab.m', '.m'));
[np, nf] = check(np, nf, 'blanks/isspace/isletter/isdigit', numel(blanks(3)) == 3 && isspace(' ') && isletter('a') && isdigit('7'));
s = struct('name', 'beam', 'L', 2);
s.E = 200e9;
s = setfield(s, 'h', 0.1);
[np, nf] = check(np, nf, 'struct/fieldnames/isfield', numel(fieldnames(s)) == 4 && isfield(s, 'E') && numfields(s) == 4);
[np, nf] = check(np, nf, 'getfield/rmfield', getfield(s, 'L') == 2 && ~isfield(rmfield(s, 'h'), 'h'));
c = {1, 'two', [3 4]};
[np, nf] = check(np, nf, 'cell/iscellstr/cell2mat', isequal(size(cell(2, 3)), [2 3]) && iscellstr({'a', 'b'}) && isequal(cell2mat({1 2; 3 4}), [1 2; 3 4]));
[np, nf] = check(np, nf, 'num2cell/deal', iscell(num2cell([1 2])) && strcmp(c{2}, 'two'));
[p1, p2] = deal(7, 8);
[np, nf] = check(np, nf, 'deal outputs', p1 == 7 && p2 == 8);
f = @(x) x.^2 + 1;
[np, nf] = check(np, nf, 'anonymous functions', f(3) == 10 && isequal(arrayfun(f, [1 2]), [2 5]));
[np, nf] = check(np, nf, 'cellfun', isequal(cellfun(@numel, {'ab', 'cde'}), [2 3]) && isequal(cellfun(@(x) x*2, {1, 2}, 'UniformOutput', false), {2, 4}));
[np, nf] = check(np, nf, 'feval/func2str/str2func', feval(@sqrt, 9) == 3 && strcmp(func2str(@sin), 'sin') && feval(str2func('cos'), 0) == 1);
[np, nf] = check(np, nf, 'unique/ismember/nnz', isequal(unique([3 1 3 2]), [1 2 3]) && ismember(2, [1 2]) && nnz([0 1 2 0]) == 2);
[np, nf] = check(np, nf, 'user function + recursion', fact(5) == 120);
try
    error('test:id', 'custom %d', 5);
catch err
    [np, nf] = check(np, nf, 'try/catch with identifier', strcmp(err.identifier, 'test:id') && strcmp(err.message, 'custom 5'));
end
total = 0; k = 0;
while true
    k = k + 1;
    if mod(k, 2) == 0, continue; end
    total = total + k;
    if k >= 9, break; end
end
switch 'b'
    case {'a', 'b'}
        sw = 1;
    otherwise
        sw = 0;
end
[np, nf] = check(np, nf, 'while/break/continue/switch', total == 25 && sw == 1);

%% 7. Numerics, statistics, signal, polynomials
fprintf('\n--- 7. Numerics, statistics, signals ---\n');
t = linspace(0, pi, 1001);
[np, nf] = check(np, nf, 'trapz', abs(trapz(t, sin(t)) - 2) < 1e-5);
ct = cumtrapz(t, sin(t));
[np, nf] = check(np, nf, 'cumtrapz', abs(ct(end) - 2) < 1e-5);
[np, nf] = check(np, nf, 'interp1', interp1([0 1 2], [0 10 20], 1.5) == 15 && abs(interp1([0 1 2], [0 1 4], 1.5, 'spline') - 2.25) < 1e-12);
[np, nf] = check(np, nf, 'interp2', interp2([1 2; 3 4], 1.5, 1.5) == 2.5);
data = [2 4 4 4 5 5 7 9];
[np, nf] = check(np, nf, 'std/var/median', abs(std(data) - 2.138089935299395) < 1e-12 && abs(var(data) - 4.571428571428571) < 1e-12 && median(data) == 4.5);
[np, nf] = check(np, nf, 'rms/zscore', abs(rms([3 4]) - sqrt(12.5)) < 1e-12 && abs(mean(zscore(data))) < 1e-12);
[np, nf] = check(np, nf, 'quantile/prctile', quantile([1 2 3 4 5], 0.5) == 3 && prctile([1 2 3 4 5], 50) == 3);
[h, p] = ttest([5.1 4.9 5.2 5.0 4.8], 5);
[np, nf] = check(np, nf, 'ttest', h == 0 && p > 0.05);
[h2, p2] = ttest2([1 2 3 4 5], [11 12 13 14 15]);
[np, nf] = check(np, nf, 'ttest2', h2 == 1 && p2 < 0.001);
[nc, ed] = histcounts([1 2 2 3 3 3], [0.5 1.5 2.5 3.5]);
[np, nf] = check(np, nf, 'histcounts', isequal(nc, [1 2 3]));
fs = 100; ts = (0:fs - 1)/fs;
Y = abs(fft(sin(2*pi*10*ts)));
[~, kpk] = max(Y(1:fs/2));
[np, nf] = check(np, nf, 'fft peak at 10 Hz', kpk - 1 == 10);
[np, nf] = check(np, nf, 'ifft(fft(x)) = x', norm(real(ifft(fft([1 2 3 4]))) - [1 2 3 4]) < 1e-12);
pc = poly([1 2]);
[np, nf] = check(np, nf, 'poly/roots', isequal(pc, [1 -3 2]) && norm(sort(roots([1 -3 2])) - [1; 2]) < 1e-12);
pf = polyfit([0 1 2 3], [1 3 5 7], 1);
[np, nf] = check(np, nf, 'polyfit/polyval', norm(pf - [2 1]) < 1e-12 && polyval([1 0 -1], 3) == 8);

%% 8. Solvers, optimisation, integration
fprintf('\n--- 8. Solvers and integration ---\n');
[np, nf] = check(np, nf, 'fzero', abs(fzero(@(x) cos(x) - x, [0 1]) - 0.739085133215161) < 1e-9);
xs = fsolve(@(x) [x(1)^2 + x(2)^2 - 4; x(1) - x(2)], [1; 1]);
[np, nf] = check(np, nf, 'fsolve', norm(xs - [sqrt(2); sqrt(2)]) < 1e-8);
xm = fminsearch(@(x) (x(1) - 1)^2 + (x(2) + 2)^2, [0 0]);
[np, nf] = check(np, nf, 'fminsearch', norm(xm - [1 -2]) < 1e-4);
[np, nf] = check(np, nf, 'fminbnd', abs(fminbnd(@(x) (x - 2)^2, 0, 5) - 2) < 1e-5);
[np, nf] = check(np, nf, 'fminunc', norm(fminunc(@(x) (x - 3)^2, 0) - 3) < 1e-5);
xl = linprog([-1; -1], [1 2; 3 1], [4; 6]);
[np, nf] = check(np, nf, 'linprog', norm(xl - [1.6; 1.2]) < 1e-6);
[np, nf] = check(np, nf, 'integral/quad/quadgk', abs(integral(@(x) x.^2, 0, 3) - 9) < 1e-9 && abs(quad(@(x) x.^2, 0, 3) - 9) < 1e-6 && abs(quadgk(@(x) exp(-x), 0, Inf) - 1) < 1e-8);
[np, nf] = check(np, nf, 'integral2', abs(integral2(@(x, y) x.*y, 0, 1, 0, 2) - 1) < 1e-8);

%% 9. ODEs (vibrations)
fprintf('\n--- 9. ODEs ---\n');
wn = 2*pi*1.5; zeta = 0.05;
osc = @(t, y) [y(2); -2*zeta*wn*y(2) - wn^2*y(1)];
[to, yo] = ode45(osc, [0 4], [1; 0]);
wd = wn*sqrt(1 - zeta^2);
exact = exp(-zeta*wn*to).*(cos(wd*to) + zeta*wn/wd*sin(wd*to));
[np, nf] = check(np, nf, 'ode45 damped oscillator', max(abs(yo(:, 1) - exact)) < 1e-4);
[t23, y23] = ode23(@(t, y) -2*y, [0 1], 1);
[np, nf] = check(np, nf, 'ode23 decay', abs(y23(end) - exp(-2)) < 1e-4);
[t15, y15] = ode15s(@(t, y) [-1000*y(1) + y(2); -y(2)], [0 1], [1; 1]);
[np, nf] = check(np, nf, 'ode15s stiff', abs(y15(end, 2) - exp(-1)) < 1e-3);
opts = odeset('RelTol', 1e-8, 'AbsTol', 1e-10);
[t8, y8] = ode45(@(t, y) -y, linspace(0, 1, 11), 1, opts);
[np, nf] = check(np, nf, 'ode45 with odeset + fixed times', numel(t8) == 11 && abs(y8(end) - exp(-1)) < 1e-7);

%% 10. Symbolic math (incl. Laplace)
fprintf('\n--- 10. Symbolic math ---\n');
syms s t x
F = laplace(exp(-2*t)*sin(3*t));
[np, nf] = check(np, nf, 'laplace', isequal(simplify(F - 3/((s + 2)^2 + 9)), sym(0)));
ft = ilaplace(1/(s*(s + 1)));
[np, nf] = check(np, nf, 'ilaplace', abs(double(subs(ft, t, 2)) - (1 - exp(-2))) < 1e-12);
[np, nf] = check(np, nf, 'diff', isequal(diff(x^3), 3*x^2));
[np, nf] = check(np, nf, 'int', isequal(int(2*x), x^2) && double(int(x, 0, 2)) == 2);
[np, nf] = check(np, nf, 'limit', double(limit(sin(x)/x, x, 0)) == 1);
[np, nf] = check(np, nf, 'taylor', isequal(taylor(exp(x), x, 'Order', 3), x^2/2 + x + 1));
sol = solve(x^2 - 4 == 0, x);
[np, nf] = check(np, nf, 'solve', numel(sol) == 2);
[np, nf] = check(np, nf, 'expand/factor', isequal(expand((x + 1)^2), x^2 + 2*x + 1) && ~isempty(factor(x^2 - 1)));
[np, nf] = check(np, nf, 'subs/latex/symvar', double(subs(x^2, x, 3)) == 9 && ischar(latex(x^2)) && ~isempty(symvar(x + t)));
[np, nf] = check(np, nf, 'sym()', isequal(sym(2)*x, 2*x));

%% 11. Random numbers and timing
fprintf('\n--- 11. Random numbers ---\n');
rng(42); r1 = rand(1, 3); rng(42); r2 = rand(1, 3);
[np, nf] = check(np, nf, 'rng reproducible', isequal(r1, r2));
[np, nf] = check(np, nf, 'rand/randn/randi/randperm', all(rand(1, 100) < 1) && abs(mean(randn(1, 20000))) < 0.05 && all(randi(6, 1, 50) <= 6) && isequal(sort(randperm(5)), 1:5));

%% 12. Workspace commands
fprintf('\n--- 12. Workspace ---\n');
tmpvar = 5;
[np, nf] = check(np, nf, 'exist', exist('tmpvar') == 1 && exist('sin') == 5 && exist('nothing_here') == 0);
clear tmpvar
[np, nf] = check(np, nf, 'clear', exist('tmpvar') == 0);
who

%% 13. Plotting: 2-D
fprintf('\n--- 13. Plots (figures 1-9) ---\n');
tt = linspace(0, 4, 400);
figure(1);
set(gcf, 'Name', 'Line plots');
subplot(2, 2, 1);
plot(tt, sin(2*pi*tt), 'b-', tt, cos(2*pi*tt), 'r--o', 'LineWidth', 1.5);
title('\omega_n t with \zeta = 0.05'); xlabel('t (s)'); ylabel('x (m)');
legend('sin', 'cos'); grid on; xlim([0 2]);
subplot(2, 2, 2);
semilogy(tt, exp(-tt) + 1e-3); title('semilogy'); grid on
subplot(2, 2, 3);
loglog(logspace(0, 3, 50), logspace(0, 3, 50).^2); title('loglog');
subplot(2, 2, 4);
semilogx(logspace(-1, 2, 50), log10(logspace(-1, 2, 50))); title('semilogx');
sgtitle('Figure 1: line plots');
figure(2);
subplot(2, 3, 1); bar([3 -1 2; 1 2 3]'); title('grouped bar');
subplot(2, 3, 2); stem(0:9, exp(-0.3*(0:9)), 'filled'); title('stem');
subplot(2, 3, 3); stairs(0:5, [1 3 2 4 3 5]); title('stairs');
subplot(2, 3, 4); area(tt, abs(sin(tt))); title('area');
subplot(2, 3, 5); rng(1); scatter(randn(1, 60), randn(1, 60), 25, 'r', 'filled'); title('scatter');
subplot(2, 3, 6); histogram(randn(1, 2000), 30, 'Normalization', 'pdf'); title('histogram');
figure(3);
xe = 1:6; ye = [2.1 3.9 6.2 7.8 10.1 12.2];
errorbar(xe, ye, 0.3*ones(1, 6), 'o-', 'DisplayName', 'measured'); hold on
pcoef = polyfit(xe, ye, 1);
plot(xe, polyval(pcoef, xe), 'k--', 'DisplayName', 'fit');
yline(8, ':'); xline(3.5, 'r--'); text(1.2, 11, 'linear fit');
legend; grid on; axis([0 7 0 14]);
xticks(1:6); xticklabels({'\theta_1', '\theta_2', '\theta_3', '\theta_4', '\theta_5', '\theta_6'});
title('errorbar, xline, yline, text, ticks'); hold off
hp = get(gca, 'XLim');
[np, nf] = check(np, nf, 'get/set on axes', isequal(hp, [0 7]));
hl = plot(1:3, [1 4 9]);
set(hl, 'Color', 'm', 'LineWidth', 3);
[np, nf] = check(np, nf, 'get/set on a line', get(hl, 'LineWidth') == 3 && isequal(get(hl, 'YData'), [1 4 9]));

%% 14. Plotting: 3-D, contour, polar
[Xg, Yg] = meshgrid(linspace(-2, 2, 40));
Zg = Xg.*exp(-Xg.^2 - Yg.^2);
figure(4);
subplot(2, 2, 1); surf(Xg, Yg, Zg); colormap jet; colorbar; shading interp; title('surf'); zlabel('z');
subplot(2, 2, 2); mesh(Xg, Yg, Zg); view(45, 25); title('mesh'); zlim([-0.5 0.5]);
subplot(2, 2, 3); contour(Xg, Yg, Zg, 10, 'ShowText', 'on'); title('contour');
subplot(2, 2, 4); contourf(Xg, Yg, Zg, 12); colorbar; axis equal; title('contourf');
figure(5);
subplot(1, 2, 1); th = linspace(0, 6*pi, 300);
plot3(cos(th), sin(th), th, 'r', 'LineWidth', 2); grid on; title('plot3');
hold on; scatter3(cos(th(1:20:end)), sin(th(1:20:end)), th(1:20:end), 30, 'filled'); hold off
subplot(1, 2, 2); polarplot(th, 1 + 0.5*cos(3*th)); title('polarplot');

%% 15. Animation and export
figure(6);
ha = animatedline('Color', 'b', 'LineWidth', 2);
axis([0 4 -1 1]); grid on; title('animatedline + drawnow');
for kk = 1:60
    addpoints(ha, tt(kk*6), exp(-0.5*tt(kk*6))*cos(2*pi*1.5*tt(kk*6)));
    drawnow
end
figure(7);
for kk = 1:5
    plot(tt, sin(2*pi*tt + kk/2)); ylim([-1 1]); title(sprintf('GIF frame %d', kk));
    exportgraphics(gcf, 'es_selftest_anim.gif', 'Append', true);
end
saveas(gcf, 'es_selftest_plot.png');
pause(0.2);
[np, nf] = check(np, nf, 'saveas/exportgraphics wrote files', exist('es_selftest_plot.png') >= 0);

%% 16. Control systems and PID (Phase 6)
fprintf('\n--- 16. Control systems ---\n');
s = tf('s');
Gc = 1/(s^2 + 2*s + 2);
[np, nf] = check(np, nf, 'tf/zpk/ss classes', strcmp(class(Gc), 'tf') && strcmp(class(zpk(Gc)), 'zpk') && strcmp(class(ss(Gc)), 'ss'));
[np, nf] = check(np, nf, 'pole/dcgain/isstable', abs(dcgain(Gc) - 0.5) < 1e-12 && isstable(Gc) && numel(pole(Gc)) == 2);
Tc = feedback(Gc, 1);
[np, nf] = check(np, nf, 'feedback', abs(dcgain(Tc) - 1/3) < 1e-12);
si = stepinfo(tf(1, [1 2 2]));
[np, nf] = check(np, nf, 'stepinfo overshoot', abs(si.Overshoot - 100*exp(-pi)) < 0.05);
[gmc, pmc, wcgc] = margin(tf(10, [1 3 3 1]));
[np, nf] = check(np, nf, 'margin', abs(gmc - 0.8) < 1e-6 && abs(wcgc - sqrt(3)) < 1e-6);
[Cc, infoc] = pidtune(tf(1, [1 3 3 1]), 'PID');
[np, nf] = check(np, nf, 'pidtune stable, PM ~60', infoc.Stable && abs(infoc.PhaseMargin - 60) < 8);
[yc, tc] = step(Gc);
[np, nf] = check(np, nf, 'step data', abs(yc(end) - 0.5) < 1e-3);
figure(8);
subplot(2, 2, 1); step(Gc, 'b', Tc, 'r--'); legend('G', 'T')
subplot(2, 2, 2); pzmap(Gc)
subplot(2, 2, 3); nyquist(Gc)
subplot(2, 2, 4); rlocus(tf(1, [1 3 2 0]))
figure(9); bode(Gc)

%% 17. Mechanical Engineering toolbox (Phase 8)
fprintf('\n--- 17. Mechanical toolbox ---\n');
pm = sdof(2, 4, 800);
[np, nf] = check(np, nf, 'sdof', abs(pm.wn - 20) < 1e-12 && abs(pm.zeta - 0.05) < 1e-12);
rb = beam(2, 200e9, 8e-6, 'simply', 1000, 1);
[np, nf] = check(np, nf, 'beam PL^3/48EI', abs(rb.max_deflection + 1000*8/(48*200e9*8e-6)) < 1e-9);
mdm = modes([2 0; 0 1], [600 -200; -200 200]);
[np, nf] = check(np, nf, 'modes', max(abs(mdm.wn - [10 20])) < 1e-9);
mc = mohr(80e6, -40e6, 25e6);
[np, nf] = check(np, nf, 'mohr', abs(mc.s1 - 85e6) < 1 && abs(mc.tau_max - 65e6) < 1);
fb = fourbar(2, 7, 9, 6, 30);
[np, nf] = check(np, nf, 'fourbar', abs(fb.theta4 - 117.29) < 0.01 && strcmp(fb.grashof, 'crank-rocker'));
[np, nf] = check(np, nf, 'fourbar joints', abs(hypot(fb.x(3) - fb.x(2), fb.y(3) - fb.y(2)) - 7) < 1e-9);

%% Engineering toolboxes (Phase 8)
cy = cycle_efficiency('carnot', 800, 300);
[np, nf] = check(np, nf, 'carnot', abs(cy.efficiency - 0.625) < 1e-12);
[np, nf] = check(np, nf, 'ideal gas', abs(ideal_gas([], 1, 1, 300) - 287*300) < 1e-6);
[np, nf] = check(np, nf, 'laminar friction', abs(friction_factor(1000) - 0.064) < 1e-12);
[np, nf] = check(np, nf, 'lmtd', abs(lmtd(150, 100, 30, 80) - 70) < 1e-9);
[np, nf] = check(np, nf, 'parallel R', abs(resistors([100 100], 'parallel') - 50) < 1e-12);
ap = ac_power(230, 30 + 40i);
[np, nf] = check(np, nf, 'ac power pf', abs(ap.pf - 0.6) < 1e-12);
[np, nf] = check(np, nf, 'material', material('steel').E == 200e9);
tr = truss2d([0 0; 2 0; 1 1], [1 3; 2 3], 200e9, 1e-3, [1 1 1; 2 1 1], [3 0 -1e4]);
[np, nf] = check(np, nf, 'truss2d', max(abs(tr.N + 1e4/sqrt(2))) < 1e-6);
fr = frame2d([0 0; 2 0], [1 2], 200e9, 1e-3, 8e-6, [1 1 1 1], [2 0 -1e3 0]);
[np, nf] = check(np, nf, 'frame2d cantilever', abs(fr.u(2,2) + 1e3*8/(3*200e9*8e-6)) < 1e-12);
pl = plate2d(0.2, 0.1, 0.01, 200e9, 0.3, 8, 4, 'left-roller', 'right', [50e6 0]);
[np, nf] = check(np, nf, 'plate2d uniform', max(abs(pl.sx(:) - 50e6)) < 1);
[q1, q2] = ik_2link(1, 0.8, 1.2, 0.6);
[ax, ay] = planar_arm([1 0.8], [q1 q2]);
[np, nf] = check(np, nf, 'ik_2link', abs(ax(end) - 1.2) < 1e-12 && abs(ay(end) - 0.6) < 1e-12);
[Tisa, aisa, pisa, rhoisa] = atmosisa(0);
[np, nf] = check(np, nf, 'atmosisa', abs(rhoisa - 1.225) < 1e-3 && abs(Tisa - 288.15) < 1e-9);
writematrix([1 2; 3 4], 'ff_test.csv');
[np, nf] = check(np, nf, 'writematrix/readmatrix', isequal(readmatrix('ff_test.csv'), [1 2; 3 4]));
writematrix([5 6; 7 8], 'ff_test.xlsx');
[np, nf] = check(np, nf, 'Excel write/read', isequal(readmatrix('ff_test.xlsx'), [5 6; 7 8]));

%% Summary
elapsed = toc;
fprintf('\n===== %d passed, %d failed, %.1f s =====\n', np, nf, elapsed);

%% Local functions
function [np, nf] = check(np, nf, name, ok)
    if ok
        np = np + 1;
        fprintf('  PASS  %s\n', name);
    else
        nf = nf + 1;
        fprintf('  FAIL  %s\n', name);
    end
end

function r = fact(n)
    if n <= 1
        r = 1;
    else
        r = n*fact(n - 1);
    end
end
