"""Task definitions and goal checks, independent of model and executor."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectTask:
    operation: str
    object_type: str
    object_id: str | None = None
    allowed_actions: tuple[str, ...] = ("OPEN", "CLOSE", "PICKUP")

    def __post_init__(self):
        if self.operation not in {"OPEN", "CLOSE", "PICKUP"}:
            raise ValueError(f"Unsupported task operation: {self.operation}")
        if not self.object_type:
            raise ValueError("Task requires an object type")
        if not self.allowed_actions or set(self.allowed_actions) - {"OPEN", "CLOSE", "PICKUP"}:
            raise ValueError("Task has unsupported or empty allowed_actions")
        if self.operation not in self.allowed_actions:
            raise ValueError("Task operation must be allowed")

    @property
    def description(self):
        verb = {"OPEN": "Open", "CLOSE": "Close", "PICKUP": "Pick up"}[self.operation]
        return f"{verb} the {self.object_type}."

    def targets(self, metadata):
        return [obj for obj in metadata["objects"]
                if obj["objectType"] == self.object_type
                and (self.object_id is None or obj["objectId"] == self.object_id)]

    def complete(self, metadata):
        inventory = {item["objectId"] for item in metadata.get("inventoryObjects", [])}
        for obj in self.targets(metadata):
            if self.operation == "PICKUP":
                if obj.get("isPickedUp") and obj["objectId"] in inventory:
                    return True
            elif obj.get("openable") and obj.get("isOpen") == (self.operation == "OPEN"):
                return True
        return False
