% for/while/if/switch, break, continue
s = 0;
for i = 1:10
    if mod(i, 2) == 0, continue, end
    if i > 7, break, end
    s = s + i;
end
fprintf('%d\n', s);
n = 0; k = 27;
while k ~= 1
    if mod(k, 2) == 0
        k = k / 2;
    else
        k = 3*k + 1;
    end
    n = n + 1;
end
fprintf('%d\n', n);
for c = [1 2; 3 4]
    fprintf('%d,%d\n', c(1), c(2));
end
x = 3;
switch x
    case {1, 2}
        disp('low')
    case 3
        disp('three')
    otherwise
        disp('other')
end
cmd = 'stop';
switch cmd
    case 'go'
        fprintf('go\n');
    case {'stop', 'halt'}
        fprintf('stopping\n');
end
t = 5;
if t < 3
    r = 'a';
elseif t < 6
    r = 'b';
else
    r = 'c';
end
fprintf('%s\n', r);
