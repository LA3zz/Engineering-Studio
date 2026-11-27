% user functions: recursion, nargin/nargout, varargin/varargout
fprintf('%d\n', fact(5));
[s, p] = sp(3, 4);
fprintf('%d %d\n', s, p);
fprintf('%d\n', sp(3, 4));
[a, b, c] = multi(1, 2, 3);
fprintf('%d %d %d\n', a, b, c);
fprintf('%d %d\n', defarg(1), defarg(1, 2));

function r = fact(n)
    if n <= 1
        r = 1;
    else
        r = n * fact(n - 1);
    end
end

function [s, p] = sp(a, b)
    s = a + b;
    if nargout > 1
        p = a * b;
    end
end

function varargout = multi(varargin)
    for i = 1:nargout
        varargout{i} = varargin{i} * 2;
    end
end

function r = defarg(a, b)
    if nargin < 2
        b = 10;
    end
    r = a + b;
end
