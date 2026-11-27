% symbolic: command syntax, diff, subs, int
syms x
f = x^2 + 3*x;
g = diff(f, x);
fprintf('%s\n', char(g));
fprintf('%d\n', double(subs(g, x, 2)));
fprintf('%s\n', char(int(x, x)));
