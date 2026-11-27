s = struct('name', 'Ada', 'age', 36);
fieldnames(s)
words = strsplit('the quick brown fox');
lens = cellfun(@numel, words)
upper(strjoin(words, '-'))
squares = arrayfun(@(x) x^2, 1:5)
[tf, loc] = ismember([3 7], [1 3 5])
rng(1); r = rand(3,3)
tic; sum(1:1e6); toc