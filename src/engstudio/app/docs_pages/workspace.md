# Workspace browser

A live table of variables: name, class, size and a short preview. Click a header to sort,
type in the filter box to narrow the list, right-click for Clear Selected (or Delete) and Clear All, and
double-click a row to display the variable in the [Command Window](command-window.md).

**Save...** writes the selected variables (or all of them) to a MATLAB `.mat` file and
**Load...** reads one back (files made by MATLAB work too). The same from scripts:
`save results x y`, `load results`, `S = load('results.mat')`. Logical arrays come back as
0/1 numbers; function handles, symbolic values and control systems cannot be saved (they are
skipped with a warning).

[Back to index](index.md)
