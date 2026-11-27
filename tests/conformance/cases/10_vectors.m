% sort/find/reductions/constructors
x = [3 1 4 1 5 9 2 6];
[s, i] = sort(x);
fprintf('%d ', s); fprintf('\n');
fprintf('%d ', i); fprintf('\n');
fprintf('%d ', find(x > 4)); fprintf('\n');
fprintf('%d %d\n', sum(x), prod([1 2 3 4]));
fprintf('%g\n', mean(x));
[m, k] = max(x);
fprintf('%d %d\n', m, k);
fprintf('%d ', cumsum(1:5)); fprintf('\n');
fprintf('%d ', diff([1 4 9 16])); fprintf('\n');
fprintf('%d ', any([0 0 1]), all([1 1 0])); fprintf('\n');
fprintf('%g ', linspace(0, 1, 5)); fprintf('\n');
fprintf('%d ', unique([3 1 2 3 1])); fprintf('\n');
r = reshape(1:6, 2, 3);
fprintf('%d ', r(2,:)); fprintf('\n');
fprintf('%d ', repmat([1 2], 1, 2)); fprintf('\n');
fprintf('%d ', fliplr(1:4)); fprintf('\n');
