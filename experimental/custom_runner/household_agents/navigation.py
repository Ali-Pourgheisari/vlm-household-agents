"""Explicit navigation controls; no search, path planning, or teleportation."""
NAVIGATION = {
    "MOVE_AHEAD": {"action": "MoveAhead", "moveMagnitude": 0.25},
    "MOVE_BACK": {"action": "MoveBack", "moveMagnitude": 0.25},
    "ROTATE_LEFT": {"action": "RotateLeft", "degrees": 45},
    "ROTATE_RIGHT": {"action": "RotateRight", "degrees": 45},
    "LOOK_UP": {"action": "LookUp", "degrees": 30},
    "LOOK_DOWN": {"action": "LookDown", "degrees": 30},
}
