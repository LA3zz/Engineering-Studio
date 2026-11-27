# Current Folder

A file tree for the working folder. Use Up or Browse, or type a path in the path box.
Double-click a `.m` file to open it in the [Script editor](script-editor.md), or a `.esmodel`
file to open it in the model editor. The folder is remembered between sessions.

The Current Folder is the working folder, as in MATLAB: relative file names in scripts and the
Command Window (`readmatrix('data.csv')`, `saveas(gcf, 'plot.png')`, `sim('model')`) refer to
it. `cd folder`, `cd ..` or `cd('C:\data')` change it (the panel follows) and `pwd` returns
it. Reading commands also look next to the running script, so a script finds its own data.

[Back to index](index.md)
