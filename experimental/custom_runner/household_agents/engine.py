"""Task-agnostic orchestration, bounded recovery, and evidence capture."""
from PIL import Image

from .artifacts import save, state
from .executor import ActionExecutor
from .model import OutputValidationError


def run_interaction(controller, task, model, output, max_retries=2, result=None):
    if not isinstance(max_retries, int) or not 0 <= max_retries <= 5:
        raise ValueError("max_retries must be between 0 and 5")
    output.mkdir(parents=True, exist_ok=True)
    if result is None:
        result = {}
    result.update(task=task.description, operation=task.operation, object_type=task.object_type,
                  object_id=task.object_id, attempts=[], max_retries=max_retries,
                  action_executed=False, task_success=False,
                  first_attempt_success=False, recovered=False, already_satisfied=False)
    executor = ActionExecutor(controller)
    result["allowed_actions"] = list(task.allowed_actions)
    result["camera"] = controller.last_event.metadata.get("agent")
    result["before"] = [state(obj) for obj in task.targets(controller.last_event.metadata)]
    Image.fromarray(controller.last_event.frame).save(output / "before.png")
    feedback = None
    try:
        if task.complete(controller.last_event.metadata):
            result.update(task_success=True, already_satisfied=True)
            return result
        for index in range(max_retries + 1):
            folder = output / f"attempt_{index + 1:02d}"
            folder.mkdir()
            event = controller.last_event
            Image.fromarray(event.frame).save(folder / "before.png")
            save(folder / "visible_objects.json", [state(obj) for obj in event.metadata["objects"] if obj.get("visible")])
            choices = executor.legal_choices(task)
            save(folder / "legal_choices.json", choices)
            attempt = {"number": index + 1, "action_executed": False,
                       "task_success": False, "feedback_received": feedback,
                       "failure_stage": "validation"}
            result["attempts"].append(attempt)
            print(f"Attempt {index + 1}/{max_retries + 1}: {task.description}", flush=True)
            try:
                if not choices:
                    raise ValueError("No eligible visible action/object pairs; navigation is outside this demo")
                attempt.update(model.choose(task.description, choices, feedback, folder))
                action, name = attempt["parsed"]["action"], attempt["parsed"]["object"]
                attempt["failure_stage"] = "precondition"
                command = executor.command(action, name, task)
                attempt["simulator_command"] = command
                save(folder / "simulator_command.json", command)
                attempt["failure_stage"] = "execution"
                print(f"Executing: {command}", flush=True)
                attempt["action_executed"] = result["action_executed"] = True
                attempt.update(executor.execute(action, command))
                if attempt["execution_error"]:
                    raise ValueError(attempt["execution_error"])
                attempt["failure_stage"] = "goal"
                if not task.complete(controller.last_event.metadata):
                    raise ValueError(f"Action executed, but task is incomplete: {task.description}")
                attempt.update(task_success=True)
                attempt.pop("failure_stage")
                result.update(task_success=True, first_attempt_success=index == 0, recovered=index > 0)
            except ValueError as exc:
                if isinstance(exc, OutputValidationError):
                    attempt.update(model_response=exc.response, usage=exc.usage)
                attempt["error"] = str(exc)
                feedback = {"previous_response": attempt.get("model_response"),
                            "failure_stage": attempt["failure_stage"], "error": str(exc),
                            "previous_command": attempt.get("simulator_command")}
                print(f"Rejected/failed: {exc}", flush=True)
            except Exception as exc:
                attempt.update(failure_stage="runtime", error=str(exc))
                raise
            finally:
                Image.fromarray(controller.last_event.frame).save(folder / "after.png")
                save(folder / "result.json", attempt)
                result["after"] = [state(obj) for obj in task.targets(controller.last_event.metadata)]
                save(output / "result.json", result)
            if result["task_success"]:
                return result
        raise RuntimeError(f"Retry budget exhausted after {len(result['attempts'])} attempts; task incomplete")
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        Image.fromarray(controller.last_event.frame).save(output / "after.png")
        result["after"] = [state(obj) for obj in task.targets(controller.last_event.metadata)]
        result["inventory_after"] = controller.last_event.metadata.get("inventoryObjects", [])
        save(output / "result.json", result)
