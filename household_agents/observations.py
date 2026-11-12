"""Simulator-assisted camera labels, kept separate from interaction eligibility."""
from types import SimpleNamespace

from .executor import ActionExecutor


def camera_observations(event, task, choices):
    detections = getattr(event, 'instance_detections2D', None)
    if detections is None:
        raise ValueError('Camera observations require renderInstanceSegmentation=True')
    objects = []
    evidence = []
    goal_objects = []
    target_ids = {obj['objectId'] for obj in task.targets(event.metadata)}
    executor = ActionExecutor(SimpleNamespace(last_event=event))
    eligible_ids = {
        action: {obj['objectId'] for obj in executor.candidates(action, task)}
        for action in choices
    }
    for obj in sorted(event.metadata['objects'], key=lambda item: (item['objectType'], item['objectId'])):
        if obj['objectId'] not in detections:
            continue
        box = detections[obj['objectId']]
        if box is None or len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
            continue
        # No world positions, IDs, image coordinates, distances, or route hints
        # are included in model-visible observations.
        observation = {
            'object': obj['objectType'], 'in_view': True,
            'interaction_status': 'currently_interactable' if obj.get('visible') else 'not_currently_interactable',
            'eligible_actions': [action for action, names in choices.items()
                                 if obj['objectType'] in names and obj['objectId'] in eligible_ids[action]],
        }
        for capability, state_key in (('toggleable', 'isToggled'), ('openable', 'isOpen'), ('pickupable', 'isPickedUp')):
            if obj.get(capability):
                observation[capability] = True
                observation[state_key] = bool(obj.get(state_key))
        objects.append(observation)
        if obj['objectId'] in target_ids:
            goal_objects.append(observation)
        evidence.append({'objectId': obj['objectId'], 'bbox': [int(n) for n in box],
                         'simulator_visible_flag': bool(obj.get('visible'))})
    return ({'goal_object': task.object_type, 'goal_object_in_view': bool(goal_objects),
             'goal_observations': goal_objects, 'objects_in_view': objects},
            {'source': 'instance_detections2D + object metadata', 'rendered_instances': evidence})
