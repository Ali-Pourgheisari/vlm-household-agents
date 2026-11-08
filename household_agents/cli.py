"""CLI wiring; model, executor and goal logic live in reusable modules."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

from ai2thor.controller import Controller

from .artifacts import save
from .engine import run_interaction
from .model import OllamaModel
from .setup import prepare_view
from .tasks import ObjectTask

PROJECT = Path(__file__).resolve().parents[1]


def main(fridge_example=False):
    parser = argparse.ArgumentParser(description="Reusable screenshot → VLM → parser → simulator interaction")
    parser.add_argument("--model", default="llava:7b")
    parser.add_argument("--max-retries", type=int, choices=range(6), default=2)
    parser.add_argument("--scene", default="FloorPlan1")
    if not fridge_example:
        parser.add_argument("--action", choices=("OPEN", "CLOSE", "PICKUP"), required=True)
        parser.add_argument("--object", required=True, help="Exact simulator object type, e.g. Cabinet or CreditCard")
        parser.add_argument("--object-id", help="Optional exact simulator instance")
    parser.add_argument("--no-setup", action="store_true", help="Use the initial view/state without scripted camera positioning")
    args = parser.parse_args()
    task = ObjectTask("OPEN" if fridge_example else args.action,
                      "Fridge" if fridge_example else args.object,
                      None if fridge_example else args.object_id)
    output = PROJECT / "results" / datetime.now(timezone.utc).strftime("interaction_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True)
    result = {"scene": args.scene, "model": args.model, "setup": [], "task_success": False}
    controller = None
    print(f"Artifacts: {output}", flush=True)
    try:
        controller = Controller(scene=args.scene, width=640, height=480, gridSize=0.25,
                                snapToGrid=False, visibilityDistance=1.5)
        if not args.no_setup:
            task = replace(task, object_id=prepare_view(controller, task, result["setup"]))
        run_interaction(controller, task, OllamaModel(args.model), output, args.max_retries, result)
        print("Task completed; screenshots and attempt history saved.", flush=True)
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        save(output / "result.json", result)
        print(json.dumps(result, indent=2), flush=True)
        if controller is not None:
            controller.stop()
