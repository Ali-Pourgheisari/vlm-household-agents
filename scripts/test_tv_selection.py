"""Repeat near-TV goal trials with fresh scenes; setup never turns the TV on."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ai2thor.controller import Controller
import httpx
from household_agents.artifacts import save, state
from household_agents.episode import goal_prompt, minimal_goal_prompt, run_episode
from household_agents.executor import ActionExecutor, BRIDGE
from household_agents.model import OllamaModel
from household_agents.navigation import NAVIGATION
from household_agents.perception import TargetLocator
from household_agents.tasks import ObjectTask

# Pose already verified by the independent feasibility diagnostic, not supplied
# to the VLM. No object interaction is performed during setup.
POSITION = {'x': -2.25, 'y': 0.9026566743850708, 'z': 5.5}
YAW = 351.96786213283264
HORIZON = 32.288995612310536


def start_pose(controller, backoff):
    if backoff == 0:
        return {'action': 'TeleportFull', 'position': dict(POSITION),
                'rotation': {'x': 0, 'y': YAW, 'z': 0}, 'horizon': HORIZON, 'standing': True}
    tv = next(obj for obj in controller.last_event.metadata['objects'] if obj['objectType'] == 'Television')
    target = tv['position']
    baseline_distance = math.sqrt(sum((POSITION[key] - target[key]) ** 2 for key in ('x', 'y', 'z')))
    desired = baseline_distance + backoff
    nominal = dict(POSITION)
    nominal['x'] -= backoff * math.sin(math.radians(YAW))
    nominal['z'] -= backoff * math.cos(math.radians(YAW))
    event = controller.step(action='GetReachablePositions')
    if not event.metadata['lastActionSuccess']:
        raise RuntimeError('Could not query free starting positions: ' + event.metadata['errorMessage'])
    candidates = []
    for point in event.metadata['actionReturn']:
        distance = math.sqrt(sum((point[key] - target[key]) ** 2 for key in ('x', 'y', 'z')))
        if abs(distance - desired) <= .15:
            candidates.append((sum((point[key] - nominal[key]) ** 2 for key in ('x', 'z')), point))
    if not candidates:
        raise RuntimeError(f'No free pose within 0.15 m of desired TV distance {desired:.3f} m')
    point = min(candidates, key=lambda item: item[0])[1]
    yaw = math.degrees(math.atan2(target['x'] - point['x'], target['z'] - point['z'])) % 360
    return {'action': 'TeleportFull', 'position': point,
            'rotation': {'x': 0, 'y': yaw, 'z': 0}, 'horizon': HORIZON, 'standing': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', type=int, choices=range(1, 21), default=5)
    parser.add_argument('--max-steps', type=int, choices=range(1, 101), default=5)
    parser.add_argument('--model', default='qwen3-vl:8b-instruct')
    parser.add_argument('--base-url', default='http://127.0.0.1:11435')
    parser.add_argument('--backoff', type=float, default=0, help='Metres behind the verified near-TV pose (0–3)')
    parser.add_argument('--step-fixture', '--one-step-fixture', dest='step_fixture', type=Path,
                        help='Verified N-step result.json from calibrate_tv_step.py (old option retained as alias)')
    protocol = parser.add_mutually_exclusive_group()
    protocol.add_argument('--scene-observations', action='store_true',
                        help='Add simulator-assisted labels for rendered objects, separate from interaction eligibility')
    protocol.add_argument('--locate-before-action', action='store_true',
                        help='Ask the VLM to locate the target before each action, with target-loss recovery feedback')
    parser.add_argument('--action-prompt', choices=('standard', 'minimal'), default='standard',
                        help='Action instruction variant; standard preserves the existing protocol')
    args = parser.parse_args()
    if not 0 <= args.backoff <= 3:
        parser.error('--backoff must be between 0 and 3 metres')
    fixture = None
    if args.step_fixture:
        if args.backoff != 0:
            parser.error('--step-fixture cannot be combined with --backoff')
        fixture = json.loads(args.step_fixture.read_text())
        if not fixture.get('verified') or fixture.get('scene') != 'FloorPlan201' or fixture.get('movement_command') != NAVIGATION['MOVE_AHEAD']:
            parser.error('Fixture must verify FloorPlan201 forward moves with the current movement command')
        if type(fixture.get('required_forward_steps', 1)) is not int or not 1 <= fixture.get('required_forward_steps', 1) <= 10:
            parser.error('Fixture required_forward_steps must be between 1 and 10')
    position = dict(POSITION)
    position['x'] -= args.backoff * math.sin(math.radians(YAW))
    position['z'] -= args.backoff * math.cos(math.radians(YAW))
    output = PROJECT / 'results' / datetime.now(timezone.utc).strftime('tv_selection_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    summary = {'scene': 'FloorPlan201', 'goal': 'Turn on the TV.', 'model': args.model,
               'base_url': args.base_url, 'planned_trials': args.trials,
               'max_decisions_per_trial': args.max_steps, 'trials': [],
               'scene_observations': args.scene_observations,
               'locate_before_action': args.locate_before_action,
               'action_prompt': args.action_prompt,
               'scope': 'Distance-controlled TV goal trials; scripted initial camera setup',
               'pose_policy': 'Baseline pose at 0; nearest reachable pose within 0.15 m of baseline distance plus backoff otherwise',
               'backoff_metres': args.backoff,
               'nominal_setup_pose': {'position': position, 'yaw': YAW, 'horizon': HORIZON}}
    with httpx.Client(timeout=10) as client:
        version = client.get(args.base_url.rstrip('/') + '/api/version')
        version.raise_for_status()
        tags = client.get(args.base_url.rstrip('/') + '/api/tags')
        tags.raise_for_status()
        summary['server_version'] = version.json()
        summary['model_metadata'] = next(m for m in tags.json()['models'] if m['name'] == args.model)
    if fixture:
        summary['required_forward_steps'] = fixture.get('required_forward_steps', 1)
        summary['pose_policy'] = f"Verified {summary['required_forward_steps']}-step calibration fixture; no setup interactions"
        summary['fixture_provenance'] = {'path': str(args.step_fixture.resolve()),
            'sha256': hashlib.sha256(args.step_fixture.read_bytes()).hexdigest(),
            'verified_setup': fixture['fixture']}
    save(output / 'summary.json', summary)
    print(f'Batch artifacts: {output}', flush=True)
    for index in range(args.trials):
        controller = None
        trial = {'trial': index + 1, 'setup_success': False, 'goal_success': False,
                 'action_prompt': args.action_prompt}
        summary['trials'].append(trial)
        folder = output / f'trial_{index + 1:02d}'
        folder.mkdir()
        try:
            setup_label = f"verified {summary['required_forward_steps']}-step start" if fixture else f'backoff {args.backoff} m'
            print(f'Trial {index + 1}/{args.trials}: fresh scene, {setup_label}', flush=True)
            controller = Controller(scene='FloorPlan201', width=640, height=480,
                                    gridSize=.25, snapToGrid=False, rotateStepDegrees=45,
                                    visibilityDistance=1.5, renderInstanceSegmentation=args.scene_observations)
            setup_command = fixture['fixture']['setup_command'] if fixture else start_pose(controller, args.backoff)
            trial['setup_command'] = setup_command
            event = controller.step(**setup_command)
            if not event.metadata['lastActionSuccess']:
                raise RuntimeError('Camera setup failed: ' + event.metadata['errorMessage'])
            tv = next(obj for obj in event.metadata['objects'] if obj['objectType'] == 'Television')
            trial['setup_tv'] = state(tv)
            trial['inventory_before'] = event.metadata['inventoryObjects']
            if not tv['toggleable'] or tv['isToggled'] or tv['isBroken']:
                raise RuntimeError('Initial TV must be functional, toggleable, and off')
            if not fixture and args.backoff == 0 and not tv['visible']:
                raise RuntimeError('Near-TV baseline must start with an interactable TV')
            if trial['inventory_before']:
                raise RuntimeError('Initial inventory must be empty')
            if fixture and tv['visible']:
                raise RuntimeError('Step fixture must start outside TV interaction range')
            trial['setup_success'] = True
            task = ObjectTask('TOGGLE_ON', 'Television', tv['objectId'],
                              allowed_actions=tuple(BRIDGE) + tuple(NAVIGATION), instruction=summary['goal'])
            trial['initial_legal_choices'] = ActionExecutor(controller).legal_choices(task)
            trial['initial_tv_interactable'] = 'Television' in trial['initial_legal_choices'].get('TOGGLE_ON', [])
            # Every trial starts with empty model history. All normal eligible
            # interaction and navigation controls remain available.
            model = OllamaModel(args.model, base_url=args.base_url,
                                prompt_builder=minimal_goal_prompt if args.action_prompt == 'minimal' else goal_prompt)
            run_episode(controller, task, model, folder, max_steps=args.max_steps, result=trial,
                        scene_observations=args.scene_observations,
                        target_locator=TargetLocator(model) if args.locate_before_action else None)
            first = trial['decisions'][0] if trial['decisions'] else {}
            trial['first_decision_success'] = bool(first.get('goal_success'))
            trial['first_choice'] = first.get('parsed')
            decisions = trial['decisions']
            trial['one_step_then_toggle_success'] = bool(trial['goal_success']
                and not trial['initial_tv_interactable'] and len(decisions) == 2
                and decisions[0].get('parsed', {}).get('action') == 'MOVE_AHEAD'
                and decisions[0].get('simulator_success')
                and decisions[1].get('parsed', {}).get('action') == 'TOGGLE_ON'
                and decisions[1].get('parsed', {}).get('object') == 'Television'
                and decisions[1].get('simulator_success'))
            expected_steps = summary.get('required_forward_steps', 1)
            expected_actions = ['MOVE_AHEAD'] * expected_steps + ['TOGGLE_ON']
            trial['exact_step_then_toggle_success'] = bool(trial['goal_success']
                and not trial['initial_tv_interactable']
                and [d.get('parsed', {}).get('action') for d in decisions] == expected_actions
                and all(d.get('simulator_success') for d in decisions)
                and decisions[-1].get('parsed', {}).get('object') == 'Television')
            if trial['exact_step_then_toggle_success']:
                for count in range(1, expected_steps + 1):
                    (folder / f'after_move_{count:02d}.png').write_bytes(
                        (folder / f'decision_{count:02d}' / 'after.png').read_bytes())
                (folder / 'middle.png').write_bytes((folder / f'decision_{expected_steps:02d}' / 'after.png').read_bytes())
        except Exception as exc:
            trial['error'] = str(exc)
            print(f'Trial error: {exc}', flush=True)
        finally:
            save(folder / 'result.json', trial)
            if controller is not None:
                controller.stop()
            summary['completed_trials'] = len(summary['trials'])
            summary['valid_setups'] = sum(t['setup_success'] for t in summary['trials'])
            summary['successful_trials'] = sum(t['goal_success'] for t in summary['trials'])
            summary['first_decision_successes'] = sum(t.get('first_decision_success', False) for t in summary['trials'])
            summary['one_step_then_toggle_successes'] = sum(t.get('one_step_then_toggle_success', False) for t in summary['trials'])
            summary['exact_step_then_toggle_successes'] = sum(t.get('exact_step_then_toggle_success', False) for t in summary['trials'])
            save(output / 'summary.json', summary)
            print(f"Trial {index + 1}: success={trial['goal_success']}, "
                  f"decisions={len(trial.get('decisions', []))}, first_choice={trial.get('first_choice')}", flush=True)
    print(json.dumps({k: v for k, v in summary.items() if k != 'trials'}, indent=2), flush=True)
    if summary['successful_trials'] != args.trials:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
