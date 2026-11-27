% indexing, end, colon, logical indexing, growth, deletion
A = [1 2 3; 4 5 6; 7 8 9];
fprintf('%d\n', A(2,3));
fprintf('%d ', A(end,:)); fprintf('\n');
fprintf('%d ', A(:,1)'); fprintf('\n');
v = 10:10:50;
fprintf('%d ', v([1 end])); fprintf('\n');
fprintf('%d ', v(end:-1:3)); fprintf('\n');
v(7) = 70;
fprintf('%d ', v); fprintf('\n');
v(2) = [];
fprintf('%d\n', numel(v));
m = A(A > 5)';
fprintf('%d ', m); fprintf('\n');
A(2,:) = [];
fprintf('%d %d\n', size(A));
B = zeros(2);
B(:) = 1:4;
fprintf('%d ', B(1,:)); fprintf('\n');
