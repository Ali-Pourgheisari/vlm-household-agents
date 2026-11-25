"""Visual target location and memory, independent of action selection and execution."""
import shutil

from .artifacts import save
from .model import OutputValidationError, decode_response_object


VISIBLE_POSITIONS = ('LEFT', 'CENTER', 'RIGHT')
POSITIONS = VISIBLE_POSITIONS + ('NOT_VISIBLE', 'UNCERTAIN')
LOCATION_SCHEMA = {
    'type': 'object',
    'properties': {'target_position': {'type': 'string', 'enum': list(POSITIONS)}},
    'required': ['target_position'], 'additionalProperties': False,
}


class TargetLocator:
    def __init__(self, model):
        self.model = model

    def locate(self, target, folder, validation_error=None):
        output = folder / 'perception'
        output.mkdir()
        shutil.copyfile(folder / 'before.png', output / 'before.png')
        prompt = (
            f'Inspect this single camera screenshot. Target object: {target}.\n'
            'Locate the target in the image: LEFT, CENTER, or RIGHT according to '
            'which horizontal third contains the center of the visible target. '
            'If the target is absent use NOT_VISIBLE; if you cannot tell use UNCERTAIN.\n'
            'Use only this image. Do not invent an off-screen target location. '
            'Return only JSON with exactly target_position.'
        )
        if validation_error:
            prompt += '\nPrevious location output failed validation: ' + validation_error
        raw = self.model.image_response(prompt, LOCATION_SCHEMA, output)
        text = raw.get('message', {}).get('content', '')
        usage = {key: raw.get(key) for key in ('prompt_eval_count', 'eval_count', 'done', 'done_reason')}
        try:
            location = decode_response_object(raw, ('target_position',))
            if not isinstance(location['target_position'], str) or location['target_position'] not in POSITIONS:
                raise ValueError('Unsupported target_position; choose from ' + ', '.join(POSITIONS))
        except ValueError as exc:
            save(output / 'result.json', {'error': str(exc), 'model_response': text, 'usage': usage})
            raise OutputValidationError(str(exc), text, usage) from exc
        result = {'location': location, 'model_response': text, 'usage': usage}
        save(output / 'result.json', result)
        return result


class TargetTracker:
    """Keep model-estimated target locations; never infer hidden coordinates."""
    def __init__(self):
        self.previous = None
        self.last_seen = None

    def observe(self, location, decision, task, choices):
        current = {'target_position': location['target_position'], 'at_decision': decision}
        visible = current['target_position'] in VISIBLE_POSITIONS
        if visible:
            self.last_seen = dict(current)
        interaction_available = task.object_type in choices.get(task.operation, [])
        phase = ('interact' if interaction_available else 'approach' if visible
                 else 'recover' if self.last_seen else 'locate')
        feedback = {
            'target': task.object_type, 'current': current, 'previous': self.previous,
            'last_seen': self.last_seen, 'phase': phase,
            'target_lost': not visible and self.last_seen is not None,
            'goal_interaction': {'action': task.operation, 'object': task.object_type,
                                 'available': interaction_available},
        }
        self.previous = dict(current)
        return feedback
