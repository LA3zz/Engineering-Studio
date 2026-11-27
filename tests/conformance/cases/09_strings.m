% string functions
s = 'Hello World';
fprintf('%s\n', upper(s));
fprintf('%d\n', length(s));
fprintf('%s\n', strrep(s, 'World', 'MATLAB'));
fprintf('%d\n', strcmp(s, 'Hello World'));
parts = strsplit('a,b,c', ',');
fprintf('%d %s\n', numel(parts), parts{2});
fprintf('%s\n', strjoin(parts, '-'));
fprintf('%s\n', strtrim('   pad  '));
fprintf('%d\n', str2double('3.5') * 2);
fprintf('%s\n', num2str(pi, 4));
x = ['ab', 'cd'];
fprintf('%s\n', x);
fprintf('%s\n', mat2str([1 2; 3 4]));
fprintf('%d\n', strfind('abcabc', 'bc'));
