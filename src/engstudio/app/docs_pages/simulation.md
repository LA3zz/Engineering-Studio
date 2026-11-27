# Simulation (block diagrams)

Build a block diagram, press **Run**, and see the results in Scope windows, like Simulink.

## The model editor

- Open it with **Simulation > New Model** or **Simulation > Open Model...**, by double-clicking an
  `.esmodel` file in the Current Folder panel, or with `open_system('model.esmodel')`.
- **Add blocks:** drag them from the Library (left) onto the canvas, or double-click a library
  entry.
- **Wire:** drag from an output port (filled circle, right side) to an input port (open circle,
  left side). A new wire into an input replaces the old one.
- **Edit:** double-click a block for its parameters (vectors as `[1 2 1]`, matrices as
  `[0 1; -4 -0.4]`, `inf` allowed). Double-click a Subsystem to edit its contents.
- **Delete** removes the selection; **Ctrl+Z / Ctrl+Y** undo and redo; **Ctrl+S** saves.
- **Run (Ctrl+R)**, **Stop**, **Settings (Ctrl+E)**: start/stop time, solver (`ode45`, `ode23`,
  `ode15s`, `ode113`, fixed-step `rk4`, `euler`), tolerances, maximum and fixed step.

## Blocks

| Library | Blocks |
|---|---|
| Sources | Step, Sine Wave, Ramp, Clock, Pulse Generator, Constant, From Workspace |
| Sinks | Scope, To Workspace, Display, Terminator |
| Math Operations | Gain, Sum, Product, Abs, Math Function |
| Continuous | Integrator, Transfer Fcn, State-Space, Derivative, PID Controller, Transport Delay |
| Discrete | Unit Delay, Zero-Order Hold, Discrete Transfer Fcn, Discrete-Time Integrator |
| Discontinuities | Saturation, Dead Zone, Relay |
| Signal Routing | Switch |
| User-Defined Functions | Fcn (expression of `u`, `u(1)`, `t`, e.g. `u^2 + sin(t)`) |
| Ports & Subsystems | Subsystem, Inport, Outport |

Every feedback loop needs a block with state (Integrator, Transfer Fcn with more poles than
zeros, Unit Delay, ...); otherwise the run stops with an "algebraic loop" message naming the
blocks.

## From scripts

```
out = sim('mass_spring_damper.esmodel');        % run, results in a struct
plot(out.tout, out.x); grid on                  % To Workspace block 'x'
sim('pid_position_loop', 'StopTime', 5)         % no output: plots the Scopes, sets out
```

Options: `'StartTime'`, `'StopTime'`, `'Solver'`, `'RelTol'`, `'AbsTol'`, `'MaxStep'`,
`'FixedStep'`. Example models are in `examples/models` (mass-spring-damper, PID position loop,
sampled-data control) and `examples/simulation_example.m` runs them.

[Back to index](index.md)
