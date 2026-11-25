"""Ordered object tasks in one continuing scene, using the shared interaction engine."""
from PIL import Image

from .artifacts import save, state
from .engine import run_interaction


def run_procedure(controller, tasks, model, output, max_retries=2, result=None):
    if not tasks:
        raise ValueError("A procedure requires at least one task")
    if not isinstance(max_retries, int) or not 0 <= max_retries <= 5:
        raise ValueError("max_retries must be between 0 and 5")
    output.mkdir(parents=True, exist_ok=True)
    if result is None:
        result = {}
    result.update(procedure=[task.description for task in tasks], steps=[], checkpoints=[],
                  procedure_success=False, max_retries_per_step=max_retries,
                  scope="Supplied task sequence; VLM selects actions for each step in one scene")

    def checkpoint(filename, label):
        event = controller.last_event
        Image.fromarray(event.frame).save(output / filename)
        ids = {obj['objectId'] for task in tasks for obj in task.targets(event.metadata)}
        result['checkpoints'].append({
            'label': label, 'image': filename,
            'objects': [state(obj) for obj in event.metadata['objects'] if obj['objectId'] in ids],
            'camera': event.metadata.get('agent'),
        })
        save(output / 'result.json', result)

    try:
        checkpoint('before.png', 'Before procedure')
        for index, task in enumerate(tasks):
            print(f"Procedure step {index + 1}/{len(tasks)}: {task.description}", flush=True)
            step_result = {}
            result['steps'].append(step_result)
            # No reset, camera movement, or demo setup between steps.
            run_interaction(controller, task, model, output / f'step_{index + 1:02d}',
                            max_retries, step_result)
            checkpoint(f'checkpoint_{index + 1:02d}.png', f'After step {index + 1}: {task.description}')
            if index == 0 and len(tasks) == 2:
                Image.fromarray(controller.last_event.frame).save(output / 'middle.png')
        result['procedure_success'] = True
        result['first_attempt_success'] = all(
            step['first_attempt_success'] or step['already_satisfied'] for step in result['steps'])
        result['model_requests'] = sum(
            sum('model_response' in attempt for attempt in step['attempts']) for step in result['steps'])
        return result
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        # On failure this is the last observed state, never proof of completion.
        checkpoint('after.png', 'Final observed state')
