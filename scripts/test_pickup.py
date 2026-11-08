"""Smoke-test a real AI2-THOR pickup without model inference."""

import json
from datetime import datetime, timezone
from pathlib import Path

from ai2thor.controller import Controller
from PIL import Image


def main():
    output = Path("results") / datetime.now(timezone.utc).strftime(
        "pickup_%Y%m%dT%H%M%S_%fZ"
    )
    output.mkdir(parents=True)
    controller = None
    attempts = []
    try:
        controller = Controller(
            scene="FloorPlan1", width=640, height=480,
            gridSize=0.25, rotateStepDegrees=90,
        )
        for view in range(8):
            event = controller.last_event
            candidates = sorted(
                (obj for obj in event.metadata["objects"]
                 if obj["visible"] and obj["pickupable"]),
                key=lambda obj: obj["distance"],
            )
            for obj in candidates:
                Image.fromarray(event.frame).save(output / "before.png")
                event = controller.step(action="PickupObject", objectId=obj["objectId"])
                attempts.append({
                    "objectId": obj["objectId"],
                    "success": event.metadata["lastActionSuccess"],
                    "error": event.metadata["errorMessage"],
                })
                if event.metadata["lastActionSuccess"]:
                    inventory = event.metadata["inventoryObjects"]
                    picked = next(item for item in event.metadata["objects"]
                                  if item["objectId"] == obj["objectId"])
                    assert picked["isPickedUp"], "Object metadata does not confirm pickup"
                    assert any(item["objectId"] == obj["objectId"] for item in inventory)
                    Image.fromarray(event.frame).save(output / "after.png")
                    result = {
                        "scene": "FloorPlan1", "action": "PickupObject",
                        "success": True, "objectType": obj["objectType"],
                        "objectId": obj["objectId"], "isPickedUp": True,
                        "inventoryObjects": inventory, "attempts": attempts,
                    }
                    (output / "result.json").write_text(json.dumps(result, indent=2))
                    print(json.dumps(result, indent=2), flush=True)
                    print(f"Artifacts: {output.resolve()}", flush=True)
                    return
            controller.step(action="RotateRight")
            if view == 3:
                controller.step(action="LookDown", degrees=30)
        raise RuntimeError("No pickup succeeded from the starting position")
    except Exception as exc:
        (output / "result.json").write_text(json.dumps({
            "success": False, "error": str(exc), "attempts": attempts,
        }, indent=2))
        raise
    finally:
        if controller is not None:
            controller.stop()


if __name__ == "__main__":
    main()
