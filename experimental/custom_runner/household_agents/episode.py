"""Goal-driven action loop, explicit goal feedback, and bounded loop recovery."""
import json

from PIL import Image

from .artifacts import save, state
from .executor import ActionExecutor
from .model import OutputValidationError
from .repetition import RepetitionMonitor, state_signature
from .observations import camera_observations
from .perception import TargetTracker


def goal_prompt(goal, choices, feedback):
    prompt = (
        f"Goal: {goal}\nCurrent camera screenshot is attached.\n"
        "Return one next simulator action as JSON with exactly action and object.\n"
        "Available actions and eligible object identifiers: " + json.dumps(choices) + "\n"
        "MOVE_AHEAD/MOVE_BACK move 0.25 meters; ROTATE_LEFT/ROTATE_RIGHT rotate 45 degrees; "
        "LOOK_UP/LOOK_DOWN tilt 30 degrees. Navigation uses object identifier None.\n"
    )
    if isinstance(feedback, dict):
        prompt += 'Current goal status: ' + json.dumps(feedback['goal_status']) + '\n'
        if feedback.get('scene_observations') is not None:
            prompt += 'Camera object observations (rendered objects and interaction eligibility are separate): ' + json.dumps(feedback['scene_observations']) + '\n'
        if feedback.get('target_tracking') is not None:
            prompt += 'VISUAL TARGET TRACKING: ' + json.dumps(feedback['target_tracking']) + '\n'
            prompt += (
                'A separate image-only model request estimated the target location; it can be wrong. '
                'Use that estimate and the current screenshot to choose one action toward the goal. '
                'In approach phase, choose a movement that approaches or aligns with the target, considering obstacles. '
                'In recover phase, the previously seen target is now lost or uncertain; choose a movement to bring it back into view. '
                'In locate phase, choose a movement to look for the target. '
                'In interact phase, the simulator lists the goal interaction as available; choose an eligible interaction to complete the goal. '
                'The next screenshot will be inspected again after your action.\n'
            )
        prompt += 'Observed action history and simulator results: ' + json.dumps(feedback['history']) + '\n'
        if feedback.get('repetition'):
            prompt += 'REPETITION FEEDBACK: ' + json.dumps(feedback['repetition']) + '\n'
    elif feedback:
        # Retain the original baseline protocol for separately labeled comparisons.
        prompt += 'Observed action history and simulator results: ' + json.dumps(feedback) + '\n'
    return prompt


def goal_status(task, metadata):
    complete = task.complete(metadata)
    return {'goal': task.description, 'complete': complete,
            'message': 'Goal complete.' if complete else f'Goal "{task.description}" remains incomplete.'}


def minimal_goal_prompt(goal, choices, feedback):
    """Compact action context; include recovery/error feedback only when needed."""
    tracking = feedback.get('target_tracking', {}) if isinstance(feedback, dict) else {}
    position = tracking.get('current', {}).get('target_position')
    prompt = f'Goal: {goal}\nCurrent screenshot is attached. '
    if position:
        prompt += f'A visual model located the target at {position}. '
    prompt += (
        'Choose one next action to make progress toward the goal.\n'
        'Eligible actions and objects: ' + json.dumps(choices) + '\n'
        'MOVE_AHEAD/MOVE_BACK move 0.25 meters; ROTATE_LEFT/ROTATE_RIGHT turn 45 degrees; '
        'LOOK_UP/LOOK_DOWN tilt 30 degrees. Navigation uses object None. '
        'Return only JSON with exactly action and object using an eligible pair.'
    )
    if isinstance(feedback, dict):
        if tracking.get('target_lost'):
            prompt += '\nThe target is lost or uncertain. Last visual sighting: ' + json.dumps(tracking.get('last_seen'))
            prompt += '. Choose one action to bring it back into view.'
        history = feedback.get('history', [])
        if history and history[-1].get('error'):
            prompt += '\nPrevious decision failed: ' + history[-1]['error']
        if feedback.get('repetition'):
            prompt += '\nRepetition feedback: ' + json.dumps(feedback['repetition'])
    return prompt


def run_episode(controller, task, model, output, max_steps=12, max_failures=3, result=None,
                enhanced_feedback=True, max_repetition_retries=2, scene_observations=False,
                target_locator=None):
    if not isinstance(max_steps, int) or not 1 <= max_steps <= 100:
        raise ValueError('max_steps must be between 1 and 100')
    if not isinstance(max_failures, int) or not 1 <= max_failures <= 10:
        raise ValueError('max_failures must be between 1 and 10')
    if not isinstance(max_repetition_retries, int) or not 0 <= max_repetition_retries <= 5:
        raise ValueError('max_repetition_retries must be between 0 and 5')
    if (scene_observations or target_locator is not None) and not enhanced_feedback:
        raise ValueError('Scene observations and target location require enhanced_feedback=True')
    output.mkdir(parents=True, exist_ok=True)
    if result is None:
        result = {}
    result.update(goal=task.description, decisions=[], goal_success=False, max_steps=max_steps,
                  max_consecutive_failures=max_failures, enhanced_feedback=enhanced_feedback,
                  max_repetition_retries=max_repetition_retries, repetition_events=[],
                  scene_observations=scene_observations,
                  locate_before_action=target_locator is not None,
                  scope='Goal-driven actions; no scripted route or positioning')
    executor = ActionExecutor(controller)
    monitor = RepetitionMonitor(state_signature(controller.last_event.metadata))
    history = []
    pending_cycle = None
    tracker = TargetTracker()
    perception_error = None
    failures = 0
    Image.fromarray(controller.last_event.frame).save(output / 'before.png')
    result['before'] = [state(obj) for obj in task.targets(controller.last_event.metadata)]
    try:
        if task.complete(controller.last_event.metadata):
            result.update(goal_success=True, stop_reason='already_satisfied')
            return result
        for index in range(max_steps):
            folder = output / f'decision_{index + 1:02d}'
            folder.mkdir()
            event = controller.last_event
            Image.fromarray(event.frame).save(folder / 'before.png')
            choices = executor.legal_choices(task)
            save(folder / 'legal_choices.json', choices)
            feedback = history
            if enhanced_feedback:
                feedback = {'goal_status': goal_status(task, event.metadata), 'history': history,
                            'repetition': pending_cycle['feedback'] if pending_cycle else None}
            if scene_observations:
                observations, evidence = camera_observations(event, task, choices)
                feedback['scene_observations'] = observations
                save(folder / 'scene_observations.json', {'model_observations': observations, 'evidence': evidence})
            save(folder / 'feedback.json', feedback)
            decision = {'number': index + 1, 'action_executed': False,
                        'failure_stage': 'validation', 'camera_before': event.metadata.get('agent')}
            result['decisions'].append(decision)
            print(f'Goal decision {index + 1}/{max_steps}', flush=True)
            try:
                if target_locator is not None:
                    decision['failure_stage'] = 'perception'
                    decision['perception'] = target_locator.locate(task.object_type, folder, perception_error)
                    perception_error = None
                    tracking = tracker.observe(decision['perception']['location'], index + 1, task, choices)
                    feedback['target_tracking'] = tracking
                    decision['target_tracking'] = tracking
                    save(folder / 'feedback.json', feedback)
                    print(f"Target location: {tracking['current']['target_position']}; phase={tracking['phase']}", flush=True)
                    decision['failure_stage'] = 'validation'
                decision.update(model.choose(task.description, choices, feedback, folder))
                action, name = decision['parsed']['action'], decision['parsed']['object']
                decision['failure_stage'] = 'precondition'
                command = executor.command(action, name, task)
                decision['simulator_command'] = command
                save(folder / 'simulator_command.json', command)
                token = (action, name, command.get('objectId'))
                decision['action_token'] = token
                if pending_cycle and token == tuple(pending_cycle['cycle']['expected_next']):
                    decision['failure_stage'] = 'repetition'
                    pending_cycle['rejections'] += 1
                    pending_cycle['event']['rejected_choices'] = pending_cycle['rejections']
                    pending_cycle['feedback'].update(
                        rejected_choices=pending_cycle['rejections'],
                        message='That choice would continue the detected unproductive cycle and was not executed. '
                                'Choose a different action using the current image and goal.')
                    raise ValueError(pending_cycle['feedback']['message'])
                decision['failure_stage'] = 'execution'
                decision['action_executed'] = True
                print(f'Model selected: {action} {name}; executing {command}', flush=True)
                decision.update(executor.execute(action, command))
                if decision['execution_error']:
                    raise ValueError(decision['execution_error'])
                decision.pop('failure_stage')
                failures = 0
            except ValueError as exc:
                if isinstance(exc, OutputValidationError):
                    if decision['failure_stage'] == 'perception':
                        perception_error = str(exc)
                        decision.update(perception_response=exc.response, perception_usage=exc.usage)
                    else:
                        decision.update(model_response=exc.response, usage=exc.usage)
                decision['error'] = str(exc)
                failures += 1
                print(f'Decision failed: {exc}', flush=True)
            except Exception as exc:
                decision.update(failure_stage='runtime', error=str(exc))
                raise
            finally:
                event = controller.last_event
                decision['camera_after'] = event.metadata.get('agent')
                decision['goal_success'] = task.complete(event.metadata)
                if enhanced_feedback:
                    decision['goal_status'] = goal_status(task, event.metadata)
                # Preserve exact baseline feedback when requested.
                if decision.get('error'):
                    history_item = {'response': decision.get('model_response', decision.get('perception_response')),
                                    'command': decision.get('simulator_command'), 'error': decision['error']}
                else:
                    parsed = decision.get('parsed', {})
                    history_item = {'action': parsed.get('action'), 'object': parsed.get('object'),
                                    'simulator_success': decision.get('simulator_success', False)}
                if enhanced_feedback:
                    history_item['goal_status'] = decision['goal_status']
                    if history_item.get('command'):
                        history_item['command'] = {key: value for key, value in history_item['command'].items()
                                                   if key != 'objectId'}
                        history_item['object'] = decision.get('parsed', {}).get('object')
                    history_item['object_after'] = decision.get('target_after')
                    # Keep coordinate-bearing IDs/evaluation metadata out of model feedback.
                    if history_item['object_after']:
                        history_item['object_after'] = {key: value for key, value in history_item['object_after'].items()
                                                       if key in ('objectType', 'isOpen', 'isToggled', 'isPickedUp')}
                history.append(history_item)
                if enhanced_feedback and decision['action_executed']:
                    if pending_cycle and not decision.get('error'):
                        pending_cycle['event']['recovered_at_decision'] = index + 1
                        pending_cycle = None
                    cycle = monitor.observe(tuple(decision['action_token']), state_signature(event.metadata))
                    if cycle and not decision['goal_success']:
                        warning = {
                            'message': 'An action cycle repeated twice and returned to the same scene state while '
                                       'the goal remained incomplete. Do not continue that cycle; choose a different action.',
                            'cycle_actions': [{'action': item[0], 'object': item[1]} for item in cycle['cycle']],
                            'rejected_choices': 0,
                        }
                        repetition_event = {'detected_at_decision': index + 1, 'cycle': cycle,
                                            'recovery_warning': dict(warning)}
                        result['repetition_events'].append(repetition_event)
                        pending_cycle = {'cycle': cycle, 'feedback': warning, 'rejections': 0,
                                         'event': repetition_event}
                        decision['repetition_detected'] = True
                        print('Unproductive cycle detected; requesting a different action.', flush=True)
                Image.fromarray(event.frame).save(folder / 'after.png')
                save(folder / 'result.json', decision)
                save(output / 'result.json', result)
            if decision['goal_success']:
                result.update(goal_success=True, stop_reason='goal_reached')
                return result
            if pending_cycle and pending_cycle['rejections'] >= max_repetition_retries:
                pending_cycle['event']['stopped_at_decision'] = index + 1
                result['stop_reason'] = 'repetition_limit'
                return result
            if failures >= max_failures:
                result['stop_reason'] = 'consecutive_failure_limit'
                return result
        result['stop_reason'] = 'decision_limit'
        return result
    except Exception as exc:
        result.update(stop_reason='runtime_error', error=str(exc))
        raise
    finally:
        result['after'] = [state(obj) for obj in task.targets(controller.last_event.metadata)]
        Image.fromarray(controller.last_event.frame).save(output / 'after.png')
        save(output / 'result.json', result)
