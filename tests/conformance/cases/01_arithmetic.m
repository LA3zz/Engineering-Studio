% precedence, unary minus, power, transpose, element-wise, mod/rem
a = 2 + 3*4^2;
b = -2^2;
c = (1:4)';
d = c' * c;
e = [1 2; 3 4] .* [5 6; 7 8];
f = mod(-7, 3);
g = rem(-7, 3);
h = 7/2;
fprintf('%d\n', a, b, d, f, g);
fprintf('%g\n', h);
fprintf('%d %d\n', e');
