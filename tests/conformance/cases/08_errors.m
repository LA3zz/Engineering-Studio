% error(), try/catch, identifiers, errors inside functions
try
    error('my:id', 'bad value %d', 42);
catch e
    fprintf('%s | %s\n', e.identifier, e.message);
end
try
    x = [1 2 3];
    y = x(5);
catch e
    fprintf('caught\n');
end
try
    error('simple message');
catch e
    fprintf('%d %s\n', isempty(e.identifier), e.message);
end
try
    check(-2.5);
catch e
    fprintf('%s\n', e.message);
end
check(1);
fprintf('done\n');

function check(v)
    if v < 0
        error('check:neg', 'negative: %g', v);
    end
end
