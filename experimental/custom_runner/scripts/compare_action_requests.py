"""Compare current/short action prompts with/without a schema on saved images."""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

import httpx

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from household_agents.artifacts import save
from household_agents.model import validate_response


CONDITIONS = [('current', True), ('current', False), ('short', True), ('short', False)]


def short_prompt(feedback, choices):
    return (
        'Goal: ' + feedback['goal_status']['goal'] + '\n'
        'Use the attached current screenshot and feedback to choose one next eligible action '
        'that makes progress toward the goal.\n'
        'Eligible actions and objects: ' + json.dumps(choices) + '\n'
        'MOVE_AHEAD/MOVE_BACK move 0.25 meters; ROTATE_LEFT/ROTATE_RIGHT turn 45 degrees; '
        'LOOK_UP/LOOK_DOWN tilt 30 degrees. Navigation uses object None.\n'
        'Feedback: ' + json.dumps(feedback) + '\n'
        'Return only JSON with exactly action and object, using one eligible action/object pair. '
        'Use exact spelling and no explanation.'
    )


def make_request(source, prompt, image_bytes, constrained):
    body = copy.deepcopy(source)
    body['messages'] = [{'role': 'user', 'content': prompt,
                         'images': [base64.b64encode(image_bytes).decode()]}]
    if not constrained:
        body.pop('format', None)
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decisions', nargs='+', type=Path,
                        help='Existing decision directories containing before.png, request.json, feedback.json, legal_choices.json')
    parser.add_argument('--base-url', default='http://127.0.0.1:11435')
    args = parser.parse_args()
    sources = []
    for path in args.decisions:
        request = json.loads((path / 'request.json').read_text())
        choices = json.loads((path / 'legal_choices.json').read_text())
        feedback = json.loads((path / 'feedback.json').read_text())
        image_bytes = (path / 'before.png').read_bytes()
        digest = hashlib.sha256(image_bytes).hexdigest()
        if request['messages'][0]['image_sha256'] != digest:
            parser.error(f'Saved image does not match original request hash: {path}')
        if not request.get('format') or request.get('stream') is not False:
            parser.error(f'Expected a saved schema-constrained nonstreaming request: {path}')
        if len(request['messages']) != 1 or request['messages'][0]['role'] != 'user':
            parser.error(f'Expected one independent user message: {path}')
        if sources and any(request.get(key) != sources[0]['request'].get(key)
                           for key in ('model', 'options', 'keep_alive', 'stream')):
            parser.error('Selected images must use the same model and inference options')
        sources.append({'path': path, 'request': request, 'choices': choices,
                        'feedback': feedback, 'image_bytes': image_bytes, 'image_sha256': digest})
    output = PROJECT / 'results' / datetime.now(timezone.utc).strftime('action_request_comparison_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    shutil.copyfile(__file__, output / 'compare_action_requests_executed.py')
    summary = {'scope': 'Saved-image prompt/schema comparison; no execution',
               'retries': 0, 'base_url': args.base_url, 'items': []}
    print(f'Artifacts: {output}', flush=True)
    with httpx.Client(timeout=600, transport=httpx.HTTPTransport(retries=0)) as client:
        for key, route in (('server_version', '/api/version'), ('models', '/api/tags')):
            response = client.get(args.base_url.rstrip('/') + route)
            response.raise_for_status()
            summary[key] = response.json()
        model = sources[0]['request']['model']
        summary['model_metadata'] = next(m for m in summary['models']['models'] if m['name'] == model)
        for source in sources:
            prior_path = source['path'].parent.parent / 'summary.json'
            if prior_path.exists():
                prior = json.loads(prior_path.read_text())
                if (prior['model_metadata']['digest'] != summary['model_metadata']['digest']
                        or prior['server_version'] != summary['server_version']):
                    raise RuntimeError('Installed model/server differs from the saved live experiment')
        save(output / 'summary.json', summary)
        for index, source in enumerate(sources, 1):
            view = output / f'view_{index:02d}'
            view.mkdir()
            (view / 'before.png').write_bytes(source['image_bytes'])
            save(view / 'feedback.json', source['feedback'])
            save(view / 'legal_choices.json', source['choices'])
            save(view / 'source_request.json', source['request'])
            prompts = {'current': source['request']['messages'][0]['content'],
                       'short': short_prompt(source['feedback'], source['choices'])}
            # Reverse the order for alternate views to reduce a fixed order confound.
            order = CONDITIONS if index % 2 else list(reversed(CONDITIONS))
            for prompt_kind, constrained in order:
                name = prompt_kind + ('_schema' if constrained else '_unconstrained')
                folder = view / name
                folder.mkdir()
                (folder / 'before.png').write_bytes(source['image_bytes'])
                prompt = prompts[prompt_kind]
                (folder / 'prompt.txt').write_text(prompt + '\n')
                body = make_request(source['request'], prompt, source['image_bytes'], constrained)
                saved = {**body, 'messages': [{'role': 'user', 'content': prompt,
                         'image_file': 'before.png', 'image_sha256': source['image_sha256']}]}
                save(folder / 'request.json', saved)
                item = {'view': index, 'source': str(source['path'].resolve()),
                        'condition': name, 'constrained': constrained, 'prompt_kind': prompt_kind,
                        'image_sha256': source['image_sha256'],
                        'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                        'folder': str(folder.relative_to(output)), 'valid': False}
                print(f'View {index}/{len(sources)}: {name}', flush=True)
                try:
                    response = client.post(args.base_url.rstrip('/') + '/api/chat', json=body)
                    (folder / 'raw_response.json').write_text(response.text)
                    response.raise_for_status()
                    raw = response.json()
                    if raw.get('error'):
                        raise ValueError(raw['error'])
                    text = raw.get('message', {}).get('content', '')
                    item['raw_text'] = text
                    item['usage'] = {key: raw.get(key) for key in
                                     ('prompt_eval_count', 'eval_count', 'done', 'done_reason')}
                    (folder / 'response.txt').write_text(text)
                    try:
                        action, obj, _ = validate_response(raw, source['choices'])
                        item.update(valid=True, parsed={'action': action, 'object': obj})
                    except ValueError as exc:
                        item['validation_error'] = str(exc)
                    print(json.dumps({key: item[key] for key in ('raw_text', 'valid', 'parsed', 'validation_error') if key in item}), flush=True)
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    item['request_error'] = str(exc)
                    print(f'Request failed: {exc}', flush=True)
                summary['items'].append(item)
                save(folder / 'result.json', item)
                save(output / 'summary.json', summary)
    print(f'Completed {len(summary["items"])} requests. Artifacts: {output}', flush=True)
    return 2 if any(item.get('request_error') for item in summary['items']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
