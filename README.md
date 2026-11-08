# VLM Household Agents

**Work in progress.**

This project experiments with vision-language models (VLMs) as agents for
household tasks in AI2-THOR. The authors are **Ali Pourgheisari** and
**Mehran Rajabi**.

## Credits and related projects

- [AsgardBench](https://github.com/microsoft/AsgardBench) provides the
  embodied household-task benchmark and evaluation code.
- [AI2-THOR](https://ai2thor.allenai.org/) provides the interactive simulator.
- [Ollama](https://ollama.com/) provides the local model-serving endpoint.
- [LLaVA](https://llava-vl.github.io/) is the vision-language model used for
  the initial local experiment.

AsgardBench remains an external dependency. Its source, virtual environment,
and Git history are deliberately not copied into this repository.

Project history, bugs, fixes, experiment results, and remaining work are recorded
in [progress.md](progress.md).

## Installation and reproducibility

This project expects AsgardBench beside it:

```text
/data/5pourghe/
├── AsgardBench/
└── vlm-household-agents/
```

The exact AsgardBench revision used to establish this project is recorded in
[`asgardbench-commit.txt`](asgardbench-commit.txt). For a clean reproduction,
clone AsgardBench, check out that revision, and install its dependencies:

```bash
cd /data/5pourghe
git clone https://github.com/microsoft/AsgardBench.git
cd AsgardBench
git checkout "$(cat ../vlm-household-agents/asgardbench-commit.txt)"
uv sync
```

Do not install or modify the shared Ollama installation. Start Ollama
separately if it is not already running and ensure the `llava:7b` model is
available.

## Run the project scripts

Run from this repository's root so the scripts' relative image paths remain
consistent:

```bash
cd /data/5pourghe/vlm-household-agents

# Render AI2-THOR screenshots and rotate once.
xvfb-run -a uv run --project /data/5pourghe/AsgardBench \
  python scripts/test_environment.py

# Send environment_test/01_before.png to Ollama's OpenAI-compatible endpoint.
uv run --project /data/5pourghe/AsgardBench \
  python scripts/test_vision.py

# Pick up a visible object and verify simulator inventory (no model inference).
xvfb-run -a uv run --project /data/5pourghe/AsgardBench \
  python scripts/test_pickup.py
```

The environment script saves screenshots to
`environment_test/01_before.png` and `environment_test/02_after_rotation.png`.
These generated files are ignored by Git. The `results/` directory is reserved
for benchmark outputs and other generated results.

## Run a model-selected interaction

The generic entry point supports OPEN, CLOSE, and PICKUP with exact simulator
object types. Run from this repository's root using the external environment:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/interact.py --action OPEN --object Cabinet

xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/interact.py --action CLOSE --object Cabinet

xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/interact.py --action PICKUP --object CreditCard
```

`scripts/interact_fridge.py` remains a thin example configuring OPEN Fridge:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/interact_fridge.py
```

Both entry points accept `--model` (default `llava:7b`), `--scene` (default
`FloorPlan1`), and `--max-retries` (default 2, range 0–5). The generic entry point
also accepts `--object-id` to select an exact instance.

Demo setup positions the camera using reachable positions and binds the task
to the selected instance. It closes an initially open target for OPEN tasks,
or opens an initially closed target for CLOSE tasks, so there is an interaction
to perform. Setup actions are recorded separately. Use `--no-setup` to use the
scene's initial view and state. Setup may fail for occluded or unreachable
objects; no autonomous navigation or search planner is implemented.

### Reusable components

| Responsibility | Module | What it owns |
| --- | --- | --- |
| Model interface | `household_agents/model.py` | Image requests, prompts, JSON schema, exact output validation, and conversion to the unchanged AsgardBench parser format |
| Action executor | `household_agents/executor.py` | Eligible objects by capability/state, instance resolution, simulator commands, errors, and action postconditions |
| Task definition | `household_agents/tasks.py` | Goal operation, target type/optional ID, allowed actions, and task completion checks |

`household_agents/engine.py` connects these components and manages screenshots,
the shared retry budget, feedback, and per-attempt evidence. `setup.py` and
`cli.py` handle optional scripted demo setup and command-line wiring.

For an already running AI2-THOR controller, the same engine can be called directly
from Python with the repository root on the import path:

```python
from pathlib import Path
from household_agents.engine import run_interaction
from household_agents.model import OllamaModel
from household_agents.tasks import ObjectTask

# controller is an existing AI2-THOR Controller; this call does no demo setup.
task = ObjectTask("PICKUP", "Apple", allowed_actions=("PICKUP",))
result = run_interaction(
    controller, task, OllamaModel(), Path("results/apple_demo"), max_retries=2
)
```

Use a fresh output directory for each run. Without an instance ID, any matching
object can satisfy the task; execution resolves the nearest eligible matching
instance. With an ID, other instances of that type are excluded. An already
satisfied goal finishes without a model request or simulator interaction.

### Validation, recovery, and artifacts

The VLM receives a JSON schema requiring exactly `action` and `object` with
legal enums. Application validation additionally checks that the action/object
pair is eligible (an apple is not a legal OPEN target), all fields are present,
there are no duplicate/extra fields, and generation ended normally. Only valid
choices are converted to `Action: ACTION OBJECT` for the existing parser.

OPEN/CLOSE require a visible openable object in the opposite state. PICKUP
requires a visible pickupable object and an empty hand. The executor checks
current preconditions again before sending the command, does not use
`forceAction`, and verifies simulator feedback and the commanded object's state.
Pickup verification requires both `isPickedUp` and the exact ID in inventory.
Task completion is checked separately; a successful action on the wrong object
does not establish task success.

One initial attempt and up to `--max-retries` additional attempts share a single
budget. Invalid output, failed preconditions, simulator rejection, unexpected
state, or an incomplete goal produces feedback for the next model request with
the actual error, previous response/command, fresh image, and refreshed legal
choices. Transport/HTTP/runtime failures stop the run without automatic retries.
Missing fields are never filled in and model choices are never substituted.
Retries stop immediately on success or fail once the budget is exhausted.

Each run saves root `before.png` and final `after.png`, plus one `attempt_XX/`
directory per attempt. Attempts contain screenshots, eligible object choices,
prompt, schema, image hash, raw response, parser input when valid, simulator
command when issued, and result metadata. Results distinguish first-attempt,
recovered, and already-satisfied success. CLI outputs are written to ignored
`results/interaction_<UTC timestamp>/` directories.

Run offline tests without simulator or VLM requests:

```bash
uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B -m unittest discover -s tests -v
```

## Run the benchmark sanity check

Configure the OpenAI-compatible endpoint for AsgardBench. For Ollama, the
endpoint and credential-free local key are:

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
```

Then run the two-task sanity check through AsgardBench's own `uv` environment
(not a copied environment):

```bash
cd /data/5pourghe/AsgardBench
xvfb-run -a uv run python -m AsgardBench.Model.model_tester \
  --test magt_benchmark_sanity \
  --model llava:7b
```

The benchmark writes task traces and `test_results.json` below
`AsgardBench/Test/magt_benchmark_sanity/`. Do not run the full benchmark unless
you intentionally choose to do so.

## Scope

The shared engine supports bounded OPEN/CLOSE/PICKUP interaction attempts and
object-state goals. Demo camera setup is scripted. It does not implement
autonomous navigation, a general multi-step planner, or actions such as PUT,
SLICE, or TOGGLE. The official benchmark remains external and unchanged.
No script trains a model. Generated screenshots and results remain local and
ignored by Git. See [progress.md](progress.md) for results, known issues, and
investigation reports.
