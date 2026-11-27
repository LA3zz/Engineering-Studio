% numerical builtins against analytic values
xs = 0:0.5:2;
fprintf('%.6f\n', trapz(xs, xs.^2));
fprintf('%.6f\n', integral(@(x) x.^2, 0, 3));
fprintf('%.6f\n', fzero(@(x) x^2 - 2, [0 2]));
p = polyfit(1:4, [3 5 7 9], 1);
fprintf('%.4f %.4f\n', p);
fprintf('%d ', polyval([1 0 -1], [2 3])); fprintf('\n');
fprintf('%.4f ', sort(roots([1 -3 2]))); fprintf('\n');
[t, y] = ode45(@(t, y) -y, [0 1], 1);
fprintf('%.4f\n', y(end));
fprintf('%.4f\n', interp1([1 2 3], [10 20 30], 2.5));
fprintf('%.4f\n', std([2 4 4 4 5 5 7 9]));
fprintf('%.4f\n', median([3 1 2 10]));
