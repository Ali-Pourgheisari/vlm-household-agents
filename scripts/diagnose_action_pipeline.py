"""Controlled saved-image, prompt, control, sampling, and runtime probes; no execution."""
import argparse
import base64
import copy
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
from pathlib import Path
import shutil
import sys

import httpx

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from household_agents.artifacts import save
from household_agents.episode import goal_prompt
from household_agents.model import decode_response_object, output_schema, validate_response
from household_agents.navigation import NAVIGATION


def cases_for(source, view, tracking_fields=False):
    folder = Path(source)
    request = json.loads((folder / 'request.json').read_text())
    choices = json.loads((folder / 'legal_choices.json').read_text())
    feedback = json.loads((folder / 'feedback.json').read_text())
    goal = feedback['goal_status']['goal']
    original = request['messages'][0]['content']
    image = folder / 'before.png'
    assert hashlib.sha256(image.read_bytes()).hexdigest() == request['messages'][0]['image_sha256']
    assert goal_prompt(goal, choices, feedback) == original
    result = []

    def add(name, prompt=original, image_path=image, legal=choices, schema=None, options=None, expected=None):
        body = copy.deepcopy(request)
        body['messages'] = [{'role': 'user', 'content': prompt}]
        body['format'] = schema if schema is not None else output_schema(legal)
        if options:
            body['options'].update(options)
        result.append({'name': f'v{view}_{name}', 'request': body,
                       'image_path': str(image_path.resolve()) if image_path is not None else None,
                       'choices': legal, 'source': str(folder.resolve()), 'expected_action': expected})

    add('baseline')
    if tracking_fields:
        for key in feedback['target_tracking']:
            changed = copy.deepcopy(feedback)
            changed['target_tracking'].pop(key)
            add('drop_' + key, goal_prompt(goal, choices, changed))
        changed = copy.deepcopy(feedback)
        for key in ('current', 'previous', 'last_seen'):
            if isinstance(changed['target_tracking'].get(key), dict):
                changed['target_tracking'][key].pop('at_decision', None)
        add('drop_decision_numbers', goal_prompt(goal, choices, changed))
        changed = copy.deepcopy(feedback)
        location = changed.pop('target_tracking')['current']['target_position']
        prompt = goal_prompt(goal, choices, changed)
        add('plain_location', prompt + f'\nA visual model estimates the TV position in the image as {location}.\n')
        add('range_clarification', original + '\nThe TV is rendered in the current image. Its power interaction is unavailable because it is outside interaction range.\n')
        add('baseline_end')
        return result
    no_tracking = copy.deepcopy(feedback)
    no_tracking.pop('target_tracking', None)
    add('without_tracking', goal_prompt(goal, choices, no_tracking))
    start = original.index('A separate image-only model request estimated the target location;')
    end_text = 'The next screenshot will be inspected again after your action.\n'
    end = original.index(end_text, start) + len(end_text)
    add('tracking_data_only', original[:start] + original[end:])
    no_history = copy.deepcopy(feedback)
    no_history['history'] = []
    add('without_history', goal_prompt(goal, choices, no_history))
    nav = {key: value for key, value in choices.items() if key in NAVIGATION}
    add('navigation_only', goal_prompt(goal, nav, feedback), legal=nav)
    position = feedback['target_tracking']['current']['target_position']
    for label, instruction in [('minimal_turn_on', goal), ('minimal_approach', 'Move closer to the TV.')]:
        prompt = (f'Goal: {instruction}\nCurrent screenshot is attached. '
                  f'A visual model located the TV at {position}. '
                  'Choose one next action to make progress toward the goal.\n'
                  'Eligible actions and objects: ' + json.dumps(choices) + '\n'
                  'MOVE_AHEAD/MOVE_BACK move 0.25 meters; ROTATE_LEFT/ROTATE_RIGHT turn 45 degrees; '
                  'LOOK_UP/LOOK_DOWN tilt 30 degrees. Navigation uses object None. '
                  'Return only JSON with exactly action and object using an eligible pair.')
        add(label, prompt)
    add('without_image', image_path=None)
    if view == 1:
        for other in ('LEFT', 'RIGHT'):
            changed = copy.deepcopy(feedback)
            changed['target_tracking']['current']['target_position'] = other
            changed['target_tracking']['last_seen']['target_position'] = other
            add('location_claim_' + other.lower(), goal_prompt(goal, choices, changed))
        for label, instruction, expected in [
            ('ahead', 'The target is straight ahead and the floor ahead is clear. Choose the movement that approaches it.', 'MOVE_AHEAD'),
            ('left', 'The target is to your left. Choose the movement that turns the camera toward it.', 'ROTATE_LEFT'),
            ('right', 'The target is to your right. Choose the movement that turns the camera toward it.', 'ROTATE_RIGHT'),
        ]:
            prompt = instruction + '\nControls: ' + json.dumps(nav) + '\nReturn only JSON with action and object. Navigation object is None.'
            add('text_mapping_' + label, prompt, image_path=None, legal=nav, expected=expected)
        for expected in ('MOVE_AHEAD', 'ROTATE_LEFT'):
            prompt = 'Return exactly this JSON object and nothing else: ' + json.dumps({'action': expected, 'object': 'None'})
            add('copy_' + expected.lower(), prompt, image_path=None, legal=nav, expected=expected)
        for seed in (3407, 3408, 3409):
            add(f'temperature_only_seed{seed}', options={'temperature': .7, 'seed': seed})
            add(f'qwen_sampling_seed{seed}', options={'temperature': .7, 'top_p': .8, 'top_k': 20,
                'repeat_penalty': 1.0, 'presence_penalty': 1.5, 'seed': seed})
    # Reproduce the earlier direction question on this exact image.
    movement_names = list(NAVIGATION) + ['NONE']
    direction_schema = {'type': 'object', 'properties': {
        'target_position': {'type': 'string', 'enum': ['LEFT', 'CENTER', 'RIGHT', 'NOT_VISIBLE', 'UNCERTAIN']},
        'next_movement': {'type': 'string', 'enum': movement_names}},
        'required': ['target_position', 'next_movement'], 'additionalProperties': False}
    prompt = (f'Inspect this screenshot. Where is the TV: LEFT, CENTER, RIGHT, NOT_VISIBLE, or UNCERTAIN? '
              'Choose one next movement to approach the TV. MOVE_AHEAD/MOVE_BACK move 0.25 meters; '
              'ROTATE_LEFT/ROTATE_RIGHT turn 45 degrees; LOOK_UP/LOOK_DOWN tilt 30 degrees. '
              'If the TV is absent or uncertain, use NONE. '
              'Return JSON with exactly target_position and next_movement.')
    add('direction_contract', prompt, schema=direction_schema)
    add('baseline_end')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decisions', nargs='+', type=Path)
    parser.add_argument('--base-url', default='http://127.0.0.1:11435')
    parser.add_argument('--model', help='Override model for an explicitly labeled cross-model comparison')
    parser.add_argument('--case', action='append', help='Include case names matching this shell-style pattern')
    parser.add_argument('--cpu', action='store_true', help='Request num_gpu=0; record this configuration difference')
    parser.add_argument('--tracking-fields', action='store_true', help='Sweep individual tracking fields instead of the broad probes')
    args = parser.parse_args()
    probes = [case for index, source in enumerate(args.decisions, 1) for case in cases_for(source, index, args.tracking_fields)]
    if args.case:
        probes = [case for case in probes if any(fnmatch.fnmatchcase(case['name'], pattern) for pattern in args.case)]
    if not probes:
        parser.error('No probes selected')
    output = PROJECT / 'results' / datetime.now(timezone.utc).strftime('action_pipeline_diagnosis_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    shutil.copyfile(__file__, output / 'diagnose_action_pipeline_executed.py')
    save(output / 'manifest.json', probes)
    summary = {'scope': 'Request diagnostics only; no simulator actions', 'retries': 0,
               'base_url': args.base_url, 'model_override': args.model, 'cpu': args.cpu, 'items': []}
    print(f'Artifacts: {output}', flush=True)
    with httpx.Client(timeout=600, transport=httpx.HTTPTransport(retries=0)) as client:
        for key, route in (('version', '/api/version'), ('tags', '/api/tags'), ('ps_before', '/api/ps')):
            response = client.get(args.base_url.rstrip('/') + route)
            response.raise_for_status()
            summary[key] = response.json()
        model = args.model or probes[0]['request']['model']
        response = client.post(args.base_url.rstrip('/') + '/api/show', json={'model': model})
        response.raise_for_status()
        save(output / 'model_show.json', response.json())
        save(output / 'summary.json', summary)
        for index, case in enumerate(probes, 1):
            folder = output / case['name']
            folder.mkdir()
            body = copy.deepcopy(case['request'])
            if args.model:
                body['model'] = args.model
            if args.cpu:
                body['options']['num_gpu'] = 0
            saved = copy.deepcopy(body)
            if case['image_path']:
                image_bytes = Path(case['image_path']).read_bytes()
                shutil.copyfile(case['image_path'], folder / 'before.png')
                body['messages'][0]['images'] = [base64.b64encode(image_bytes).decode()]
                saved['messages'][0].update(image_file='before.png', image_sha256=hashlib.sha256(image_bytes).hexdigest())
            save(folder / 'request.json', saved)
            (folder / 'prompt.txt').write_text(body['messages'][0]['content'] + '\n')
            item = {'name': case['name'], 'expected_action': case['expected_action'], 'source': case['source'],
                    'has_image': case['image_path'] is not None, 'valid': False}
            print(f'Probe {index}/{len(probes)}: {case["name"]}', flush=True)
            try:
                response = client.post(args.base_url.rstrip('/') + '/api/chat', json=body)
                (folder / 'raw_response.json').write_text(response.text)
                response.raise_for_status()
                raw = response.json()
                if raw.get('error'):
                    raise ValueError(raw['error'])
                text = raw.get('message', {}).get('content', '')
                item['raw_text'] = text
                item['usage'] = {key: raw.get(key) for key in ('prompt_eval_count', 'eval_count', 'done', 'done_reason')}
                (folder / 'response.txt').write_text(text)
                try:
                    if 'action' in body['format']['properties']:
                        action, obj, _ = validate_response(raw, case['choices'])
                        parsed = {'action': action, 'object': obj}
                    else:
                        schema = body['format']
                        parsed = decode_response_object(raw, tuple(schema['required']))
                        for key, value in parsed.items():
                            if not isinstance(value, str) or value not in schema['properties'][key]['enum']:
                                raise ValueError(f'Unsupported {key}: {value!r}')
                    item.update(valid=True, parsed=parsed)
                    if case['expected_action']:
                        item['expected_match'] = parsed.get('action') == case['expected_action']
                except ValueError as exc:
                    item['validation_error'] = str(exc)
                print(json.dumps({key: item[key] for key in ('raw_text', 'valid', 'expected_match', 'validation_error') if key in item}), flush=True)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                item['request_error'] = str(exc)
                print(f'Failed: {exc}', flush=True)
            summary['items'].append(item)
            save(folder / 'result.json', item)
            save(output / 'summary.json', summary)
        response = client.get(args.base_url.rstrip('/') + '/api/ps')
        response.raise_for_status()
        summary['ps_after'] = response.json()
        save(output / 'summary.json', summary)
    print(f'Completed {len(summary["items"])} probes. Artifacts: {output}', flush=True)
    return 2 if any(item.get('request_error') for item in summary['items']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
