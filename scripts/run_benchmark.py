#!/usr/bin/env python3
"""Launch the official AsgardBench runner; no custom agent loop or fallback."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--benchmark-dir', type=Path,
                        default=Path(os.environ.get('ASGARDBENCH_DIR', str(PROJECT.parent / 'AsgardBench'))))
    parser.add_argument('--test', default='magt_benchmark_sanity')
    parser.add_argument('--model', default='qwen3-vl:8b-instruct-sanity-ctx16k')
    parser.add_argument('--output-dir', type=Path, help='New output root; must not already exist')
    parser.add_argument('--dry-run', action='store_true', help='Print invocation without running or creating files')
    args, official_args = parser.parse_known_args()
    if official_args[:1] == ['--']:
        official_args = official_args[1:]
    benchmark = args.benchmark_dir.expanduser().resolve()
    if not (benchmark / 'AsgardBench/Model/model_tester.py').is_file():
        parser.error(f'AsgardBench runner not found in {benchmark}; use --benchmark-dir')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output = (args.output_dir or PROJECT / 'results' / f'official_{stamp}_{uuid.uuid4().hex[:8]}').expanduser().resolve()
    if output.exists():
        parser.error(f'Output root already exists: {output}; choose a fresh directory')
    command = ['xvfb-run', '-a', 'uv', 'run', '--project', str(benchmark), '--no-sync',
               'python', '-B', '-m', 'AsgardBench.Model.model_tester',
               '--test', args.test, '--model', args.model, *official_args]
    env = os.environ.copy()
    env.setdefault('OPENAI_BASE_URL', 'http://127.0.0.1:11435/v1')
    env.setdefault('OPENAI_API_KEY', 'ollama')
    env['ASGARDBENCH_TEST_DIR'] = str(output / 'Test')
    print(f'Working directory: {benchmark}', flush=True)
    print(f'ASGARDBENCH_TEST_DIR={env["ASGARDBENCH_TEST_DIR"]}', flush=True)
    print(shlex.join(command), flush=True)
    if args.dry_run:
        return 0
    for executable in ('xvfb-run', 'uv'):
        if shutil.which(executable) is None:
            parser.error(f'Required executable not found: {executable}')
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'runner': 'AsgardBench.Model.model_tester', 'benchmark_dir': str(benchmark),
                'test': args.test, 'model': args.model, 'command': command,
                'output_root': str(output), 'started_utc': datetime.now(timezone.utc).isoformat()}
    manifest_path = output / 'launcher.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    try:
        result = subprocess.run(command, cwd=benchmark, env=env, check=False)
    except OSError as exc:
        manifest['launch_error'] = str(exc)
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        raise
    manifest['exit_code'] = result.returncode
    manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
