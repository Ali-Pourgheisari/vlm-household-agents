"""Ask a VLM for target direction in existing images; never execute actions."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import httpx


POSITIONS = ['LEFT', 'CENTER', 'RIGHT', 'NOT_VISIBLE', 'UNCERTAIN']
MOVEMENTS = ['MOVE_AHEAD', 'MOVE_BACK', 'ROTATE_LEFT', 'ROTATE_RIGHT',
             'LOOK_UP', 'LOOK_DOWN', 'NONE']
SCHEMA = {
    'type': 'object',
    'properties': {
        'target_position': {'type': 'string', 'enum': POSITIONS},
        'next_movement': {'type': 'string', 'enum': MOVEMENTS},
    },
    'required': ['target_position', 'next_movement'],
    'additionalProperties': False,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', type=Path, nargs='+')
    parser.add_argument('--target', default='Television')
    parser.add_argument('--model', default='qwen3-vl:8b-instruct')
    parser.add_argument('--base-url', default='http://127.0.0.1:11435')
    args = parser.parse_args()
    for path in args.images:
        if not path.is_file():
            parser.error(f'Image does not exist: {path}')
    root = Path(__file__).resolve().parents[1]
    output = root / 'results' / ('direction_diagnostic_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    output.mkdir(parents=True)
    prompt = (
        f'Inspect this single camera screenshot. Target object: {args.target}.\n'
        'Locate the target in the image: LEFT, CENTER, or RIGHT according to '
        'which horizontal third contains the center of the visible target. '
        'If the target is absent use NOT_VISIBLE; if you cannot tell use UNCERTAIN.\n'
        'Choose one next camera-agent movement to approach the target using only '
        'this image. MOVE_AHEAD/MOVE_BACK translate 0.25 meters; '
        'ROTATE_LEFT/ROTATE_RIGHT turn 45 degrees; LOOK_UP/LOOK_DOWN tilt 30 degrees. '
        'NONE means no supported movement recommendation. '
        'When target_position is NOT_VISIBLE or UNCERTAIN choose NONE; '
        'do not invent an off-screen target location.\n'
        'Return only JSON with exactly target_position and next_movement. '
        'This is a screenshot diagnostic; no movement will be executed.'
    )
    summary = {'target': args.target, 'model': args.model, 'base_url': args.base_url,
               'scope': 'Independent saved-image direction proposals; no execution or physical-success claim',
               'retries': 0, 'items': []}
    (output / 'prompt.txt').write_text(prompt + '\n')
    shutil.copyfile(__file__, output / 'diagnose_direction_executed.py')
    print(f'Artifacts: {output}', flush=True)
    with httpx.Client(timeout=600, transport=httpx.HTTPTransport(retries=0)) as client:
        for key, route in (('server_version', '/api/version'), ('models', '/api/tags')):
            response = client.get(args.base_url.rstrip('/') + route)
            response.raise_for_status()
            summary[key] = response.json()
        for index, path in enumerate(args.images, 1):
            folder = output / f'image_{index:02d}'
            folder.mkdir()
            image_bytes = path.read_bytes()
            shutil.copyfile(path, folder / 'input.png')
            item = {'number': index, 'source': str(path.resolve()),
                    'image_sha256': hashlib.sha256(image_bytes).hexdigest()}
            body = {'model': args.model, 'messages': [
                        {'role': 'user', 'content': prompt,
                         'images': [base64.b64encode(image_bytes).decode()]}],
                    'format': SCHEMA,
                    'options': {'num_ctx': 16384, 'num_predict': 1024, 'temperature': 0, 'top_p': 1},
                    'stream': False, 'keep_alive': '2m'}
            saved_request = {**body, 'messages': [{'role': 'user', 'content': prompt,
                                                  'image_file': 'input.png',
                                                  'image_sha256': item['image_sha256']}]}
            (folder / 'request.json').write_text(json.dumps(saved_request, indent=2) + '\n')
            print(f'Image {index}/{len(args.images)}: {path}', flush=True)
            try:
                response = client.post(args.base_url.rstrip('/') + '/api/chat', json=body)
                (folder / 'raw_response.json').write_text(response.text)
                response.raise_for_status()
                raw = response.json()
                if raw.get('error'):
                    raise ValueError(raw['error'])
                if not raw.get('done') or raw.get('done_reason') != 'stop':
                    raise ValueError('Response did not finish normally')
                text = raw.get('message', {}).get('content', '')
                (folder / 'response.txt').write_text(text)
                def unique_pairs(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError(f'Duplicate response field: {key}')
                        result[key] = value
                    return result
                choice = json.loads(text, object_pairs_hook=unique_pairs)
                if not isinstance(choice, dict) or set(choice) != set(SCHEMA['required']):
                    raise ValueError('Response must contain exactly target_position and next_movement')
                if choice['target_position'] not in POSITIONS or choice['next_movement'] not in MOVEMENTS:
                    raise ValueError('Response contains an unsupported direction or movement')
                if choice['target_position'] in ('NOT_VISIBLE', 'UNCERTAIN') and choice['next_movement'] != 'NONE':
                    raise ValueError('Response proposed movement without a located target')
                item.update(prediction=choice, usage={key: raw.get(key) for key in
                            ('prompt_eval_count', 'eval_count', 'done', 'done_reason')})
                print(json.dumps(choice), flush=True)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                item['error'] = str(exc)
                print(f'Failed: {exc}', flush=True)
            summary['items'].append(item)
            (folder / 'result.json').write_text(json.dumps(item, indent=2) + '\n')
            (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'Completed {len(summary["items"])} images. Artifacts: {output}', flush=True)
    return 2 if any(item.get('error') for item in summary['items']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
