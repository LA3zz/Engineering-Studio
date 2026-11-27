# Script editor

Tabbed editor for `.m` scripts: Ctrl+N new, Ctrl+O open, Ctrl+S save, Ctrl+Shift+S save as,
Ctrl+W close. Unsaved changes prompt before closing. Keywords, comments (including `%{ ... %}`
block comments), strings and numbers are highlighted in both themes.

## Running

- **F5** (Run > Run Script, or the toolbar Run button) runs the whole script. Relative file
  names in the script are also looked up next to the script file.
- **F9** runs the selected text, or the current line when nothing is selected.
- **Shift+F5** (Stop) stops a running script, simulation or long calculation.
- Output appears in the [Command Window](command-window.md), variables in the
  [Workspace](workspace.md), errors with their line number in [Diagnostics](diagnostics.md),
  and figures in their own windows.

Scripts may end with local functions (`function y = f(x) ... end`).

## Call tips

While you type a function call, a tip under the cursor shows the ways to call it, with the
input you are typing now in **bold underline**. For toolbox functions it also says what that
input means, its unit, allowed values and default. Calling forms that cannot take that many
inputs are greyed out. The tip disappears when the call is closed or when you press Esc.

[Back to index](index.md)
