# Layout and themes

Drag panel title bars to move, tab or float panels; the layout is saved on exit.
View > Reset Layout (Ctrl+Shift+R) restores the default. View > Panels shows or hides
each panel. Ctrl+Shift+T toggles the light and dark themes. F11 toggles full screen.

[Back to index](index.md)

<!-- docs G7 -->
## Custom themes
Open **View > Theme > Customize...**. Pick a starting theme, then double-click a colour role
(or select it and type a hex value such as `#1f2933`, or press **Pick...**). Every change is
previewed live on the whole window. The last column warns when a text colour has less than
4.5:1 contrast against a background it is drawn on; warnings do not block saving.

Type a name and press **Save** to keep the theme. It then appears in **View > Theme** next to
Light and Dark and is remembered after a restart. **Reset to base** restores the colours of the
chosen base theme, **Delete** removes a saved theme, and **Export...** / **Import...** use a small
JSON file.

The script editor, figure windows, Diagnostics and Documentation panels follow the base theme
(Light or Dark) of a custom theme; they do not use its individual colours yet.
