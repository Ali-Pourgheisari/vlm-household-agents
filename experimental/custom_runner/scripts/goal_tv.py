"""Goal-driven TV experiment with feedback and repetition recovery; --baseline restores old feedback."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ai2thor.controller import Controller
from household_agents.artifacts import save
from household_agents.episode import goal_prompt, minimal_goal_prompt, run_episode
from household_agents.executor import BRIDGE
from household_agents.model import OllamaModel
from household_agents.navigation import NAVIGATION
from household_agents.perception import TargetLocator
from household_agents.tasks import ObjectTask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', default='FloorPlan201')
    parser.add_argument('--model', default='llava:7b')
    parser.add_argument('--base-url', default='http://localhost:11434', help='Ollama server URL')
    parser.add_argument('--max-steps', type=int, choices=range(1, 101), default=12)
    parser.add_argument('--baseline', action='store_true', help='Original history-only feedback, without repetition recovery')
    parser.add_argument('--max-repetition-retries', type=int, choices=range(6), default=2)
    parser.add_argument('--locate-before-action', action='store_true',
                        help='Ask the VLM for target location before each action')
    parser.add_argument('--action-prompt', choices=('standard', 'minimal'), default='standard')
    args = parser.parse_args()
    if args.baseline and args.locate_before_action:
        parser.error('--locate-before-action requires enhanced feedback; omit --baseline')
    if args.baseline and args.action_prompt != 'standard':
        parser.error('--baseline requires --action-prompt standard')
    output = PROJECT / 'results' / datetime.now(timezone.utc).strftime('tv_goal_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    result = {'scene': args.scene, 'model': args.model, 'base_url': args.base_url,
              'setup_actions': [], 'goal_success': False, 'action_prompt': args.action_prompt}
    controller = None
    print(f'Artifacts: {output}', flush=True)
    try:
        controller = Controller(scene=args.scene, width=640, height=480,
                                gridSize=0.25, snapToGrid=False, rotateStepDegrees=45,
                                visibilityDistance=1.5)
        task = ObjectTask('TOGGLE_ON', 'Television', allowed_actions=tuple(BRIDGE) + tuple(NAVIGATION),
                          instruction='Turn on the TV.')
        if not task.targets(controller.last_event.metadata):
            raise RuntimeError('Scene contains no Television; no model request was sent')
        model = OllamaModel(args.model, base_url=args.base_url,
                            prompt_builder=minimal_goal_prompt if args.action_prompt == 'minimal' else goal_prompt)
        run_episode(controller, task, model,
                    output, max_steps=args.max_steps, result=result, enhanced_feedback=not args.baseline,
                    max_repetition_retries=args.max_repetition_retries,
                    target_locator=TargetLocator(model) if args.locate_before_action else None)
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        save(output / 'result.json', result)
        print(json.dumps(result, indent=2), flush=True)
        if controller is not None:
            controller.stop()
    if not result['goal_success']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
