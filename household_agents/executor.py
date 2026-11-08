"""Simulator capability checks, object resolution, commands, and postconditions."""
from .artifacts import state

BRIDGE = {"OPEN": "OpenObject", "CLOSE": "CloseObject", "PICKUP": "PickupObject"}


class ActionExecutor:
    def __init__(self, controller):
        self.controller = controller

    def candidates(self, action, task):
        metadata = self.controller.last_event.metadata
        candidates = []
        for obj in metadata["objects"]:
            if not obj.get("visible"):
                continue
            # A task bound to a particular instance must not silently switch to
            # another instance of the same type.
            if (task.object_id and obj["objectType"] == task.object_type
                    and obj["objectId"] != task.object_id):
                continue
            if action in {"OPEN", "CLOSE"}:
                eligible = obj.get("openable") and obj.get("isOpen") != (action == "OPEN")
            elif action == "PICKUP":
                eligible = (obj.get("pickupable") and not obj.get("isPickedUp")
                            and not metadata.get("inventoryObjects", []))
            else:
                eligible = False
            if eligible:
                candidates.append(obj)
        return sorted(candidates, key=lambda obj: (obj.get("distance", float("inf")), obj["objectId"]))

    def legal_choices(self, task):
        choices = {}
        for action in task.allowed_actions:
            names = sorted({obj["objectType"] for obj in self.candidates(action, task)})
            if names:
                choices[action] = names
        return choices

    def command(self, action, name, task):
        if action not in task.allowed_actions or action not in BRIDGE:
            raise ValueError(f"Action is not allowed: {action}")
        matches = [obj for obj in self.candidates(action, task) if obj["objectType"] == name]
        if not matches:
            raise ValueError(f"No currently eligible visible object for {action} {name}")
        return {"action": BRIDGE[action], "objectId": matches[0]["objectId"]}

    def execute(self, action, command):
        event = self.controller.step(**command)
        obj = next((obj for obj in event.metadata["objects"]
                    if obj["objectId"] == command["objectId"]), None)
        error = None
        if not event.metadata["lastActionSuccess"]:
            error = f"Simulator rejected {action}: {event.metadata['errorMessage']}"
        elif obj is None:
            error = "Commanded object missing from resulting metadata"
        elif action == "PICKUP":
            ids = {item["objectId"] for item in event.metadata.get("inventoryObjects", [])}
            if not obj.get("isPickedUp") or obj["objectId"] not in ids:
                error = "Simulator reported success but pickup state/inventory did not match"
        elif obj.get("isOpen") != (action == "OPEN"):
            error = "Simulator reported success but target state did not match the action"
        return {"simulator_success": event.metadata["lastActionSuccess"],
                "simulator_error": event.metadata["errorMessage"],
                "target_after": state(obj) if obj else None,
                "inventory_after": event.metadata.get("inventoryObjects", []),
                "execution_error": error}
