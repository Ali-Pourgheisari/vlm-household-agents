"""Detect short repeated action cycles that return to the same world state."""
import hashlib
import json


def state_signature(metadata):
    agent = metadata.get('agent')
    if not agent:
        return None  # Without pose evidence, repeated movement is inconclusive.
    def rounded(value):
        if isinstance(value, dict):
            return {key: rounded(item) for key, item in value.items()}
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            number = round(value, 3)
            return 0 if number == 0 else number
        return value
    snapshot = {
        'pose': rounded({key: agent.get(key) for key in
                         ('position', 'rotation', 'cameraHorizon', 'isStanding')}),
        'objects': sorted((obj['objectId'], obj.get('isOpen'), obj.get('isToggled'), obj.get('isPickedUp'))
                          for obj in metadata['objects']),
        'inventory': sorted(obj['objectId'] for obj in metadata.get('inventoryObjects', [])),
    }
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


class RepetitionMonitor:
    def __init__(self, initial_state, max_period=4):
        self.states = [initial_state]
        self.actions = []
        self.max_period = max_period

    def observe(self, token, resulting_state):
        self.actions.append(token)
        self.states.append(resulting_state)
        for period in range(1, min(self.max_period, len(self.actions) // 2) + 1):
            if (self.actions[-2 * period:-period] == self.actions[-period:]
                    and resulting_state is not None
                    and self.states[-1] == self.states[-1-period] == self.states[-1-2*period]):
                cycle = self.actions[-period:]
                return {'period': period, 'cycle': cycle, 'expected_next': cycle[0],
                        'state_signature': resulting_state}
        return None
