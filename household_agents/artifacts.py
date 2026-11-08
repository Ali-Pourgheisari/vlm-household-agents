"""Local evidence serialization."""
import json


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def state(obj):
    return {key: obj.get(key) for key in (
        "objectId", "objectType", "visible", "distance", "openable", "isOpen",
        "pickupable", "isPickedUp",
    )}
