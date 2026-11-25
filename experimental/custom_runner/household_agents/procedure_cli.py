"""CLI for a supplied task sequence on a single simulator instance."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

from ai2thor.controller import Controller

from .artifacts import save
from .model import OllamaModel
from .procedure import run_procedure
from .setup import prepare_view
from .tasks import ObjectTask


def main():
    parser = argparse.ArgumentParser(description='Run ordered VLM-selected actions in one continuing scene')
    parser.add_argument('--actions', nargs='+', choices=('OPEN', 'CLOSE', 'PICKUP'), default=['OPEN', 'CLOSE'])
    parser.add_argument('--object', default='Fridge', help='Exact simulator object type')
    parser.add_argument('--object-id', help='Exact instance, if known')
    parser.add_argument('--scene', default='FloorPlan1')
    parser.add_argument('--model', default='llava:7b')
    parser.add_argument('--max-retries', type=int, choices=range(6), default=2,
                        help='Extra attempts per step (default 2)')
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / 'results' / datetime.now(timezone.utc).strftime(
        'procedure_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    result = {'scene': args.scene, 'model': args.model, 'setup': [], 'procedure_success': False}
    controller = None
    print(f'Artifacts: {output}', flush=True)
    try:
        controller = Controller(scene=args.scene, width=640, height=480, gridSize=0.25,
                                snapToGrid=False, visibilityDistance=1.5)
        first_task = ObjectTask(args.actions[0], args.object, args.object_id)
        # One scripted initial view/state setup only; all later states come from
        # the preceding model-selected interaction on this same object.
        object_id = prepare_view(controller, first_task, result['setup'])
        tasks = [replace(first_task, operation=action, object_id=object_id) for action in args.actions]
        run_procedure(controller, tasks, OllamaModel(args.model), output, args.max_retries, result)
        print('Procedure completed. Before, middle (two steps), and after screenshots saved.', flush=True)
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        save(output / 'result.json', result)
        print(json.dumps(result, indent=2), flush=True)
        if controller is not None:
            controller.stop()
