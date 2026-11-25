from pathlib import Path

from ai2thor.controller import Controller
from PIL import Image

output = Path("environment_test")
output.mkdir(exist_ok=True)

print("Starting the simulator...")

controller = Controller(
    scene="FloorPlan1",
    width=640,
    height=480,
    gridSize=0.25,
    rotateStepDegrees=90,
)

try:
    # Save the initial camera view.
    Image.fromarray(controller.last_event.frame).save(
        output / "01_before.png"
    )

    # Rotate the agent and save its new view.
    event = controller.step(action="RotateRight")
    Image.fromarray(event.frame).save(
        output / "02_after_rotation.png"
    )

    if not event.metadata["lastActionSuccess"]:
        raise RuntimeError(event.metadata["errorMessage"])

    print("SUCCESS: scene loaded, camera worked, rotation worked.")
    print(f"Screenshots saved in: {output.resolve()}")

finally:
    controller.stop()