"""Optional scripted camera and initial-state setup for demonstrations."""
import math


def prepare_view(controller, task, setup):
    """Scripted camera setup only; no model decisions or forced interactions."""
    targets = task.targets(controller.last_event.metadata)
    capability = "pickupable" if task.operation == "PICKUP" else "openable"
    targets = [obj for obj in targets if obj.get(capability)]
    if not targets:
        raise RuntimeError(f"No {capability} target for {task.description}")
    target_obj = targets[0]
    event = controller.step(action="GetReachablePositions")
    if not event.metadata["lastActionSuccess"]:
        raise RuntimeError(event.metadata["errorMessage"])
    target = target_obj["axisAlignedBoundingBox"]["center"]
    positions = sorted(event.metadata["actionReturn"], key=lambda pos:
                       (pos["x"] - target["x"]) ** 2 + (pos["z"] - target["z"]) ** 2)
    for position in positions[:80]:
        distance = math.hypot(position["x"] - target["x"], position["z"] - target["z"])
        if not 0.65 <= distance <= 1.4:
            continue
        yaw = math.degrees(math.atan2(target["x"] - position["x"],
                                      target["z"] - position["z"])) % 360
        event = controller.step(action="TeleportFull", position=position,
                                rotation={"x": 0, "y": yaw, "z": 0}, horizon=max(-30, min(60, math.degrees(math.atan2(
                                    position["y"] + 0.675 - target["y"], distance)))),
                                standing=True)
        setup.append({"action": "TeleportFull", "position": position, "yaw": yaw,
                      "success": event.metadata["lastActionSuccess"]})
        if not event.metadata["lastActionSuccess"]:
            continue
        target_obj = next(obj for obj in event.metadata["objects"]
                      if obj["objectId"] == target_obj["objectId"])
        if target_obj["visible"] and target_obj["distance"] <= 1.5:
            if task.operation in {"OPEN", "CLOSE"} and target_obj["isOpen"] == (task.operation == "OPEN"):
                setup_action = "CloseObject" if task.operation == "OPEN" else "OpenObject"
                event = controller.step(action=setup_action, objectId=target_obj["objectId"])
                setup.append({"action": setup_action, "success": event.metadata["lastActionSuccess"]})
                if not event.metadata["lastActionSuccess"]:
                    continue
            return target_obj["objectId"]
    raise RuntimeError("Could not prepare a nearby, visible target view")


