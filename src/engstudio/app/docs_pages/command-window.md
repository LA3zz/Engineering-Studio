# Command Window

Type a command and press Enter. Results without a semicolon are shown; end a line with `;` to
hide the result. Up/Down recall earlier commands (history is kept between sessions), Esc clears
the line, and pasting several lines runs them as a block. Errors are shown in red and listed
in [Diagnostics](diagnostics.md).

- `help name` shows how to call a function and what its inputs mean (`help plot`,
  `help beam`).
- `clc` clears the window, `clear` deletes variables, `who`/`whos` list them.
- `cd folder`, `cd ..` and `pwd` change and show the working folder (the
  [Current Folder](current-folder.md) panel follows).
- Command syntax works for common commands: `hold on`, `grid on`, `axis equal`,
  `close all`, `clear all`, `format long`.

While you type a call such as `plot(x, `, a tip above the input line shows what comes next
(see [Script editor](script-editor.md)).

Shortcuts: Ctrl+0 focus the Command Window, Ctrl+Shift+L clear it.

[Back to index](index.md)
