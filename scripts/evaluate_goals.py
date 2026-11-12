"""Evaluate minimal-prompt goals across fixed task and starting-view conditions."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import httpx
from PIL import Image
from ai2thor.controller import Controller
from household_agents.artifacts import save, state
from household_agents.episode import minimal_goal_prompt, run_episode
from household_agents.executor import ActionExecutor, BRIDGE
from household_agents.model import OllamaModel
from household_agents.navigation import NAVIGATION
from household_agents.perception import TargetLocator
from household_agents.tasks import ObjectTask

CASES = (
    ('tv201', 'FloorPlan201', 'TOGGLE_ON', 'Television', 'Turn on the TV.'),
    ('tv202', 'FloorPlan202', 'TOGGLE_ON', 'Television', 'Turn on the TV.'),
    ('fridge_open', 'FloorPlan1', 'OPEN', 'Fridge', 'Open the fridge.'),
    ('fridge_close', 'FloorPlan1', 'CLOSE', 'Fridge', 'Close the fridge.'),
    ('mug_pickup', 'FloorPlan1', 'PICKUP', 'Mug', 'Pick up the mug.'),
)
VARIANTS = ('near_center', 'far_target_left', 'far_target_right', 'default_start')
CONTROLLER_OPTIONS = dict(width=640, height=480, gridSize=.25, snapToGrid=False,
                          rotateStepDegrees=45, visibilityDistance=1.5,
                          renderInstanceSegmentation=True)


def angle_delta(a, b):
    return (a - b + 180) % 360 - 180


def rendered_pixels(event, object_id):
    mask = event.instance_masks.get(object_id)
    return int(mask.sum()) if mask is not None else 0


def current_target(controller, object_id):
    return next(o for o in controller.last_event.metadata['objects'] if o['objectId'] == object_id)


def camera_command(position, center, offset=0):
    distance = math.hypot(position['x'] - center['x'], position['z'] - center['z'])
    yaw = math.degrees(math.atan2(center['x'] - position['x'], center['z'] - position['z']))
    horizon = math.degrees(math.atan2(position['y'] + .675 - center['y'], distance))
    return dict(action='TeleportFull', position=position,
                rotation={'x': 0, 'y': (yaw + offset) % 360, 'z': 0},
                horizon=max(-30, min(60, horizon)), standing=True)


def prepare_start(controller, case, variant, folder):
    _, _, operation, object_type, instruction = case
    capability = {'OPEN': 'openable', 'CLOSE': 'openable', 'PICKUP': 'pickupable',
                  'TOGGLE_ON': 'toggleable'}[operation]
    targets = sorted((o for o in controller.last_event.metadata['objects']
                      if o['objectType'] == object_type and o.get(capability)),
                     key=lambda o: o['objectId'])
    if not targets:
        raise RuntimeError(f'No {capability} {object_type} in scene')
    target = targets[0]
    oid = target['objectId']
    task = ObjectTask(operation, object_type, oid,
                      allowed_actions=tuple(BRIDGE) + tuple(NAVIGATION), instruction=instruction)
    if variant == 'default_start':
        event = controller.last_event
        if task.complete(event.metadata):
            raise RuntimeError('Default-start goal already complete; no state manipulation or inference performed')
        if event.metadata.get('inventoryObjects'):
            raise RuntimeError('Default-start inventory must be empty')
        choices = ActionExecutor(controller).legal_choices(task)
        setup = {'variant': variant, 'target_id': oid, 'target_initial': state(target),
                 'target_before': state(target), 'attempts': [], 'success': True,
                 'setup_command': None, 'initial_agent': event.metadata['agent'],
                 'rendered_target_pixels': rendered_pixels(event, oid), 'initial_choices': choices,
                 'goal_interaction_initially_eligible': object_type in choices.get(operation, []),
                 'assistance': 'None: original scene pose and object state; no setup action'}
        save(folder / 'setup.json', setup)
        Image.fromarray(event.frame).save(folder / 'setup.png')
        return task, setup
    center = target['axisAlignedBoundingBox']['center']
    event = controller.step(action='GetReachablePositions')
    if not event.metadata['lastActionSuccess']:
        raise RuntimeError('GetReachablePositions failed: ' + event.metadata['errorMessage'])
    positions = event.metadata['actionReturn']
    attempts = []
    setup = {'variant': variant, 'target_id': oid, 'target_initial': state(target),
             'attempts': attempts, 'assistance': 'Initial placement and goal-opposite state only; no model route supplied'}
    save(folder / 'setup.json', setup)
    near = [p for p in positions if .65 <= math.hypot(p['x']-center['x'], p['z']-center['z']) <= 1.35]
    near.sort(key=lambda p: (abs(math.hypot(p['x']-center['x'], p['z']-center['z'])-1), p['x'], p['z']))
    anchor = None
    for position in near:
        command = camera_command(position, center)
        event = controller.step(**command)
        attempts.append({'command': command, 'success': event.metadata['lastActionSuccess']})
        if event.metadata['lastActionSuccess'] and current_target(controller, oid)['visible'] and rendered_pixels(event, oid) >= 40:
            anchor = position
            break
    if anchor is None:
        save(folder / 'setup.json', setup)
        raise RuntimeError('No eligible near view with at least 40 rendered target pixels')
    # Set an unfinished initial state using ordinary simulator interactions.
    target = current_target(controller, oid)
    initial_command = None
    if operation in ('OPEN', 'CLOSE') and target['isOpen'] == (operation == 'OPEN'):
        initial_command = {'action': 'CloseObject' if operation == 'OPEN' else 'OpenObject', 'objectId': oid}
    elif operation == 'TOGGLE_ON' and target['isToggled']:
        initial_command = {'action': 'ToggleObjectOff', 'objectId': oid}
    if initial_command:
        event = controller.step(**initial_command)
        attempts.append({'command': initial_command, 'success': event.metadata['lastActionSuccess']})
        if not event.metadata['lastActionSuccess']:
            save(folder / 'setup.json', setup)
            raise RuntimeError('Initial opposite-state setup failed: ' + event.metadata['errorMessage'])
    command = camera_command(anchor, center)
    if variant != 'near_center':
        bearing = math.degrees(math.atan2(anchor['x']-center['x'], anchor['z']-center['z']))
        # Distinct lateral positions, plus a view rotation placing the target off-center.
        desired_bearing = bearing + (25 if variant == 'far_target_left' else -25)
        offset = 35 if variant == 'far_target_left' else -35
        far = [p for p in positions if 1.8 <= math.hypot(p['x']-center['x'], p['z']-center['z']) <= 2.5]
        far.sort(key=lambda p: (abs(angle_delta(math.degrees(math.atan2(p['x']-center['x'], p['z']-center['z'])), desired_bearing))
                               + 15*abs(math.hypot(p['x']-center['x'], p['z']-center['z'])-2.1), p['x'], p['z']))
        command = None
        for position in far:
            candidate = camera_command(position, center, offset)
            event = controller.step(**candidate)
            attempts.append({'command': candidate, 'success': event.metadata['lastActionSuccess']})
            if (event.metadata['lastActionSuccess'] and not current_target(controller, oid)['visible']
                    and rendered_pixels(event, oid) >= 40):
                command = candidate
                break
        if command is None:
            save(folder / 'setup.json', setup)
            raise RuntimeError('No farther non-interactable view with at least 40 rendered target pixels')
    else:
        event = controller.step(**command)
        attempts.append({'command': command, 'success': event.metadata['lastActionSuccess']})
    if not event.metadata['lastActionSuccess'] or task.complete(event.metadata):
        raise RuntimeError('Invalid final setup or goal already completed')
    if event.metadata.get('inventoryObjects'):
        raise RuntimeError('Initial inventory must be empty')
    target = current_target(controller, oid)
    choices = ActionExecutor(controller).legal_choices(task)
    eligible = object_type in choices.get(operation, [])
    if eligible != (variant == 'near_center'):
        raise RuntimeError('Final goal interaction eligibility differs from planned starting condition')
    setup.update(success=True, setup_command=command, anchor_position=anchor,
                 initial_agent=event.metadata['agent'], target_before=state(target),
                 rendered_target_pixels=rendered_pixels(event, oid), initial_choices=choices,
                 goal_interaction_initially_eligible=eligible)
    save(folder / 'setup.json', setup)
    Image.fromarray(event.frame).save(folder / 'setup.png')
    return task, setup


def summarize(result):
    decisions = result.get('decisions', [])
    return {'goal_success': result.get('goal_success', False), 'stop_reason': result.get('stop_reason'),
            'decisions': len(decisions), 'executed_actions': sum(d.get('action_executed', False) for d in decisions),
            'failure_stages': dict(Counter(d.get('failure_stage', 'unknown') for d in decisions if d.get('error'))),
            'sequence': [d.get('parsed', {}).get('action', 'INVALID') + ' ' + d.get('parsed', {}).get('object', '') for d in decisions],
            'errors': [d['error'] for d in decisions if d.get('error')],
            'perception_requests': sum('perception' in d or 'perception_response' in d for d in decisions)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen3-vl:8b-instruct')
    parser.add_argument('--base-url', default='http://127.0.0.1:11435')
    parser.add_argument('--max-steps', type=int, choices=range(1, 101), default=20)
    parser.add_argument('--case', choices=[c[0] for c in CASES], action='append')
    parser.add_argument('--variant', choices=VARIANTS, action='append')
    parser.add_argument('--repeats', type=int, choices=range(1, 6), default=1)
    args = parser.parse_args()
    output = PROJECT / 'results' / datetime.now(timezone.utc).strftime('goal_evaluation_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    cases = [c for c in CASES if not args.case or c[0] in args.case]
    variants = args.variant or VARIANTS[:3]
    summary = {'model': args.model, 'base_url': args.base_url, 'max_decisions': args.max_steps,
               'action_prompt': 'minimal', 'locate_before_action': True,
               'planned_trials': len(cases)*len(variants)*args.repeats,
               'protocol': 'Fresh scenes; assisted conditions use scripted initial state/view, default_start uses original pose/state without setup actions; unchanged model-selected action pipeline; no trial retries',
               'setup_selection': 'Deterministic reachable-position ranking; near eligible, far ineligible; >=40 rendered target pixels. Metadata used for setup/evaluation, not target labels in model requests.',
               'controller_options': CONTROLLER_OPTIONS, 'trials': []}
    with httpx.Client(timeout=10) as client:
        for endpoint in ('version', 'tags'):
            response = client.get(args.base_url.rstrip('/') + '/api/' + endpoint)
            response.raise_for_status()
            summary['server_' + endpoint] = response.json()
    summary['model_metadata'] = next(m for m in summary['server_tags']['models'] if m['name'] == args.model)
    snapshot = output / 'source'
    for source in [Path(__file__).resolve(), *sorted((PROJECT/'household_agents').glob('*.py'))]:
        dest = snapshot / source.relative_to(PROJECT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    summary['source_sha256'] = {str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.rglob('*.py')}
    save(output/'summary.json', summary)
    print(f'Batch artifacts: {output}', flush=True)
    for case in cases:
        for variant in variants:
            for repeat in range(1, args.repeats+1):
                name = f'{case[0]}_{variant}_{repeat:02d}'
                folder = output/name
                folder.mkdir()
                trial = {'name': name, 'case': case[0], 'scene': case[1], 'operation': case[2],
                         'object_type': case[3], 'variant': variant, 'repeat': repeat,
                         'setup_success': False, 'goal_success': False}
                summary['trials'].append(trial)
                save(output/'summary.json', summary)
                controller = None
                result = {}
                started = time.monotonic()
                print(f'TRIAL {len(summary["trials"])}/{summary["planned_trials"]}: {name}', flush=True)
                try:
                    controller = Controller(scene=case[1], **CONTROLLER_OPTIONS)
                    task, setup = prepare_start(controller, case, variant, folder)
                    trial.update(setup_success=True, initial_target=setup['target_before'],
                                 initial_agent=setup['initial_agent'],
                                 goal_interaction_initially_eligible=setup['goal_interaction_initially_eligible'])
                    model = OllamaModel(args.model, args.base_url, prompt_builder=minimal_goal_prompt)
                    run_episode(controller, task, model, folder, max_steps=args.max_steps,
                                result=result, target_locator=TargetLocator(model))
                    trial.update(summarize(result))
                    trial['final_target'] = state(current_target(controller, task.object_id))
                    trial['independently_verified_goal'] = task.complete(controller.last_event.metadata)
                    if trial['goal_success'] != trial['independently_verified_goal']:
                        raise RuntimeError('Summary and actual goal state disagree')
                except Exception as exc:
                    trial.update(summarize(result))
                    trial['error'] = f'{type(exc).__name__}: {exc}'
                    if not trial['setup_success']:
                        trial['stop_reason'] = 'setup_error'
                    save(folder/'trial_error.json', trial)
                    print('TRIAL ERROR:', trial['error'], flush=True)
                finally:
                    if controller is not None:
                        controller.stop()
                    trial['elapsed_seconds'] = round(time.monotonic()-started, 3)
                    summary['completed_trials'] = len(summary['trials'])
                    summary['setup_successes'] = sum(t['setup_success'] for t in summary['trials'])
                    summary['goal_successes'] = sum(t['goal_success'] for t in summary['trials'])
                    save(folder/'trial_summary.json', trial)
                    save(output/'summary.json', summary)
                    print('TRIAL RESULT:', json.dumps(trial), flush=True)
    print('COMPLETE:', output, summary['goal_successes'], '/', summary['planned_trials'], flush=True)


if __name__ == '__main__':
    main()
