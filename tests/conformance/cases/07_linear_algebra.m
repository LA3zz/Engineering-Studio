% linear algebra against hand-derived results
A = [2 1; 1 3];
b = [3; 5];
x = A \ b;
fprintf('%.4f\n', x);
fprintf('%.4f\n', det(A));
fprintf('%.4f ', inv(A)); fprintf('\n');
e = eig(A);
fprintf('%.4f ', e); fprintf('\n');
fprintf('%d\n', rank([1 2; 2 4]));
fprintf('%.4f\n', norm([3 4]));
fprintf('%d %d\n', size(A'));
