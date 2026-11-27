% structs, nested fields, cell arrays, comma-separated lists
s.name = 'beam';
s.dims = [2 3];
s.info.id = 7;
fprintf('%s %d %d %d\n', s.name, s.dims(2), s.info.id, isfield(s, 'dims'));
t = struct('a', 1, 'b', 'xy');
names = fieldnames(t);
fprintf('%s ', names{:}); fprintf('\n');
t = rmfield(t, 'a');
fprintf('%d\n', numfields(t));
c = {1, 'two', [3 4 5]};
fprintf('%d\n', numel(c));
fprintf('%s\n', c{2});
fprintf('%d ', c{3}); fprintf('\n');
c{5} = 9;
fprintf('%d %d\n', numel(c), isempty(c{4}));
fprintf('%d\n', iscell(c) + ischar(c{2}));
