# Figures and export

Each figure opens in its own window and is updated in place when the same figure number is
drawn again. Pan and zoom with the mouse. Save a figure with Ctrl+S as PNG, SVG or PDF.

## Editing a figure in its window

- **Double-click** a title, an axis (x or y, with its label) or the plot area to open
  **Axes Properties** at that field; or use **Edit > Axes Properties...** (Ctrl+E).
- The dialog changes the figure title, axes title, x/y (and z) labels (TeX works:
  `\theta`, `x^2`), axis limits (or Auto), linear/log scales, grid, legend, equal scaling,
  and for every line its legend name, colour, line style, width and marker. With subplots,
  choose the subplot at the top. **Apply** shows the change at once.
- **Edit > Figure Title...**, **Grid On/Off** (Ctrl+G), **Legend On/Off** (Ctrl+L),
  **Undo All Changes**; **View > Reset Zoom** (Ctrl+0) and **Equal Axis Scaling**.
- Save As saves the edited figure. Edits belong to the window: if the script draws the
  same figure again, the script's version replaces them.

## Plot commands

- Figures: `figure`, `figure(n)`, `figure('Name', 'Title')`, `gcf`, `gca`, `clf`, `cla`,
  `close`, `close all`, `hold on/off`, `drawnow`.
- Lines: `plot(x, y, 'r--o', 'LineWidth', 2, 'DisplayName', 'data')`; several pairs and
  matrix columns draw several lines.
- Other 2-D types: `bar`, `stem`, `stairs`, `area`, `scatter`, `semilogx`, `semilogy`,
  `loglog`, `histogram`, `hist`, `histcounts`.
- Layout: `subplot(m, n, p)` (also `subplot(mnp)` and spans such as `subplot(2,2,[1 2])`),
  `sgtitle('Overall title')`.
- Labels: `title`, `xlabel`, `ylabel`, `legend('a', 'b')`, `legend off`, `text(x, y, 'note')`.
- Axes: `grid on/off`, `xlim([a b])`, `ylim`, `axis([x1 x2 y1 y2])`, `axis tight/equal/auto`,
  `xticks`, `xticklabels`, `set(gca, 'XTick', 1:8, 'XTickLabel', labels)`, `get(h, 'YData')`.

- 3-D and gridded data: `plot3`, `scatter3`, `surf`, `mesh`, `contour`, `contourf`,
  `zlabel`, `zlim`, `view(az, el)`, `colormap jet`, `colorbar`, `shading interp`.
  These figures open with a Matplotlib canvas (toolbar: pan, zoom, rotate, save).
- Polar and reference lines: `polarplot(theta, rho)`, `errorbar(x, y, err)`, `xline(x)`,
  `yline(y)`.
- Animation: call `drawnow` in a loop (paced to about 30 frames/s; `drawnow limitrate` skips
  frames), `pause(t)`, `h = animatedline; addpoints(h, x, y)`.
- Files: `saveas(gcf, 'plot.png')`, `print('-dpdf', 'plot')`,
  `exportgraphics(gcf, 'anim.gif', 'Append', true)` (one GIF frame per call).

Labels understand MATLAB's TeX subset: `\theta_1`, `m/s^2`, `x^{10}`, `\omega`, `90\circ`.
Use `'Interpreter', 'none'` to show text literally.

## Example

```
t = linspace(0, 2*pi, 200);
subplot(2,1,1); plot(t, sin(t), 'LineWidth', 2); grid on
title('Position'); ylabel('x (m)')
subplot(2,1,2); bar(1:4, [2 -1 3 1], 0.6); xlabel('Mode')
sgtitle('Free vibration')
```

[Back to index](index.md)
