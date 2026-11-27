"""Write the example simulation models to examples/models/*.esmodel.

Run from the project root: ``python tools/make_example_models.py``. The models are also
checked by tests/sim/test_example_models.py.
"""

from __future__ import annotations

from pathlib import Path

from engstudio.sim import serialization
from engstudio.sim.model import Block, Model, SolverSettings

OUT = Path(__file__).resolve().parents[1] / "examples" / "models"


def mass_spring_damper() -> Model:
    """m x'' + c x' + k x = F(t), m = 1 kg, c = 0.4 N s/m, k = 4 N/m, F = 1 N step at 1 s."""
    m = Model("mass_spring_damper", settings=SolverSettings(stop_time=20, max_step=0.02))
    for b in (
        Block("Force", "Step", params={"StepTime": 1.0, "Final": 1.0}, position=(20, 100)),
        Block("Sum1", "Sum", params={"Signs": "+--"}, position=(150, 100), size=(40, 60)),
        Block("InvMass", "Gain", params={"K": 1.0}, name="1/m", position=(250, 110)),
        Block("Velocity", "Integrator", name="x_dot", position=(380, 110)),
        Block("Position", "Integrator", name="x", position=(510, 110)),
        Block("Damping", "Gain", params={"K": 0.4}, name="c", position=(380, 220)),
        Block("Stiffness", "Gain", params={"K": 4.0}, name="k", position=(510, 300)),
        Block("Scope1", "Scope", params={"Title": "Displacement x (m)"}, position=(660, 110)),
        Block("ToWorkspace1", "ToWorkspace", params={"VariableName": "x"}, position=(660, 200)),
    ):
        m = m.add_block(b)
    for src, dst, dp in (("Force", "Sum1", 1), ("Sum1", "InvMass", 1), ("InvMass", "Velocity", 1),
                         ("Velocity", "Position", 1), ("Velocity", "Damping", 1),
                         ("Position", "Stiffness", 1), ("Damping", "Sum1", 2),
                         ("Stiffness", "Sum1", 3), ("Position", "Scope1", 1),
                         ("Position", "ToWorkspace1", 1)):
        m = m.connect(src, 1, dst, dp)
    return m


def pid_loop() -> Model:
    """DC motor position 0.5/(s(0.01 s + 0.1)) under PID control with a 1 rad step."""
    m = Model("pid_position_loop", settings=SolverSettings(stop_time=3, max_step=0.002))
    for b in (
        Block("Ref", "Step", params={"StepTime": 0.2}, name="reference", position=(20, 100)),
        Block("Error", "Sum", params={"Signs": "+-"}, position=(150, 100), size=(40, 50)),
        Block("PID", "PIDController", params={"P": 20.0, "I": 5.0, "D": 1.0, "N": 100.0,
                                              "UpperLimit": 24.0, "LowerLimit": -24.0},
              position=(240, 100), size=(80, 50)),
        Block("Motor", "TransferFcn", params={"Num": [0.5], "Den": [0.01, 0.1, 0.0]},
              position=(380, 100), size=(90, 50)),
        Block("Scope1", "Scope", params={"NumInputs": 2.0, "Title": "Reference and angle"},
              position=(560, 90), size=(60, 60)),
        Block("Theta", "ToWorkspace", params={"VariableName": "theta"}, position=(560, 200)),
    ):
        m = m.add_block(b)
    for src, dst, dp in (("Ref", "Error", 1), ("Error", "PID", 1), ("PID", "Motor", 1),
                         ("Motor", "Error", 2), ("Ref", "Scope1", 1), ("Motor", "Scope1", 2),
                         ("Motor", "Theta", 1)):
        m = m.connect(src, 1, dst, dp)
    return m


def sampled_control() -> Model:
    """Continuous plant 1/(s+1) with a discrete P controller behind a zero-order hold."""
    m = Model("sampled_control", settings=SolverSettings(stop_time=8, max_step=0.01))
    for b in (
        Block("Ref", "Step", params={"StepTime": 0.0}, position=(20, 100)),
        Block("Error", "Sum", params={"Signs": "+-"}, position=(140, 100), size=(40, 50)),
        Block("Sampler", "ZeroOrderHold", params={"SampleTime": 0.2}, position=(230, 100)),
        Block("Kp", "Gain", params={"K": 3.0}, position=(350, 100)),
        Block("Plant", "TransferFcn", params={"Num": [1.0], "Den": [1.0, 1.0]},
              position=(470, 100)),
        Block("Scope1", "Scope", params={"Title": "Sampled control: output"},
              position=(620, 100)),
    ):
        m = m.add_block(b)
    for src, dst, dp in (("Ref", "Error", 1), ("Error", "Sampler", 1), ("Sampler", "Kp", 1),
                         ("Kp", "Plant", 1), ("Plant", "Error", 2), ("Plant", "Scope1", 1)):
        m = m.connect(src, 1, dst, dp)
    return m


MODELS = {"mass_spring_damper": mass_spring_damper, "pid_position_loop": pid_loop,
          "sampled_control": sampled_control}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in MODELS.items():
        print("wrote", serialization.save(make(), OUT / name))
