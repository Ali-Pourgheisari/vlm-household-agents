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

## Run an ordered procedure

To open a fridge and close it afterward in the same scene:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/procedure.py --actions OPEN CLOSE --object Fridge
```

The optional scripted camera/initial-state setup runs once. Both tasks are bound
to the same exact object ID, and the controller and camera persist between
steps. Each step calls the shared interaction engine: a fresh screenshot goes
to the VLM, its actual output is validated and parsed, the executor performs the
chosen action, and the task checks the result. The next step runs only after the
previous goal succeeds. `--max-retries` applies per step (default 2 extra attempts).

Results go to `results/procedure_<UTC timestamp>/` and include:

- `before.png`: state before the first step.
- `middle.png`: state after the first step of a two-step procedure.
- `after.png`: final observed state; check `procedure_success` in `result.json`.
- `checkpoint_XX.png`: screenshot after each successfully completed step.
- `step_XX/`: complete per-step interaction and attempt evidence.

On failure, later steps are skipped and the last observed state is saved.
The sequence is supplied by the caller; the VLM chooses each interaction action
rather than independently planning the entire procedure. The reusable
`household_agents.procedure.run_procedure` accepts a list of `ObjectTask` values
and an existing controller without performing any demo setup.

## Test a goal without supplied substeps

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/goal_tv.py --max-steps 12
```

This starts FloorPlan201 at its default position and asks “Turn on the TV.”
The model receives the current screenshot, the goal, JSON output requirements,
available control names, observed action/outcome history, and explicit goal-status
feedback after each decision. Repeated unproductive cycles trigger recovery
feedback. No task
examples, route, coordinates, scripted search, teleports, or subgoals are supplied.
Unlike the supplied OPEN/CLOSE procedure, the model selects navigation as well
as object interactions. `household_agents/episode.py` manages this bounded loop;
`OllamaModel` accepts a prompt builder so the goal test avoids the full benchmark
prompt and its examples.

Movement controls are MOVE_AHEAD/MOVE_BACK (0.25 m), ROTATE_LEFT/ROTATE_RIGHT
(45 degrees), and LOOK_UP/LOOK_DOWN (30 degrees). These use `object: "None"`.
Object controls include OPEN, CLOSE, PICKUP, TOGGLE_ON, and TOGGLE_OFF when
visible simulator objects are eligible. Interaction visibility is limited to
1.5 m, so an object rendered in the image may still be too far away to appear
in the eligible object list. No off-screen object location or distance is passed
to the model. Power-goal checks inspect `isToggled` separately from action flags.

Object actions retain the unchanged AsgardBench parser. Its action vocabulary
has no navigation controls, so navigation uses a local explicit adapter after
the same strict JSON/action/object validation. Traces label which parser was
used; the benchmark parser is not modified.

The custom executor calls AI2-THOR directly and does not apply all AsgardBench
scenario rules or helper substeps. In particular, AsgardBench requires holding
a remote for TV toggles; our direct simulator command does not. FloorPlan201
contains a pickupable remote on a side table. A separate scripted diagnostic
can inspect TV/remote metadata and verify direct power-on with empty inventory:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/check_tv_feasibility.py
```

This diagnostic uses scripted positioning, saves before/after images and actual
command/state results, and is not evidence of VLM goal completion. See
[progress.md](progress.md) for the verified result and benchmark-rule distinction.

Each model decision counts toward `--max-steps` (default 12, range 1–100).
Successful navigation can continue without achieving the goal; it is not treated
as an output error. Three consecutive invalid/failed decisions stop the episode.
The loop also stops when the goal is reached; transport/runtime errors terminate
immediately. An incomplete goal exits with status 2 rather than reporting success.

### Goal feedback and repetition recovery

Goal feedback distinguishes successful execution from task completion. For
example, a successful laptop power action is followed by its observed power
state and a message that “Turn on the TV” remains incomplete. Hidden target
locations, distances, coordinate-bearing IDs, and planned routes are not supplied.

The repetition monitor looks for an action cycle of length 1–4 repeated twice,
with matching agent pose, relevant object states, and inventory at the cycle
boundaries. Pose values are rounded to 0.001 units with signed zero normalized.
A repeated MOVE_AHEAD that changes position is not flagged. Without agent pose
metadata, the detector does not assume repeated movements are unproductive.

When a cycle is detected while the goal is incomplete, the next request warns
the model and lists the observed cycle. The model must choose an alternative;
the program does not select one or remove eligible controls. A choice that would
continue the detected cycle is rejected before execution. By default, two such
rejected choices stop the episode with `stop_reason: repetition_limit`.
Use `--max-repetition-retries 0` to stop immediately on detection, or 1–5 to set
the rejection limit. Invalid outputs and other failures retain their separate
consecutive-failure limit. All requests still count toward the total decision cap.

A successful different action clears the active warning; later cycles can still
be detected. Recovery here means leaving that local cycle, not completing the
goal. Longer cycles, meaningful motion through previously visited positions,
and irrelevant actions with changing states may not be detected. The overall
step limit remains the final bound.

For the original history-only prompt without goal-status or repetition handling,
add `--baseline`. New runs record `enhanced_feedback` explicitly, so they can be
distinguished from baseline experiments. Each decision now saves `feedback.json`;
results include goal-status messages, detected cycles, recoveries, and rejected
loop-continuing choices. Existing baseline artifacts are preserved.

Evidence is saved in `results/tv_goal_<UTC timestamp>/`: root before/after
screenshots, per-decision images, actual prompts and raw responses, schema,
parser/command data, camera poses, simulator feedback, and final goal metadata.
See [progress.md](progress.md) for observed results, including failed experiments.

## Repeat reachable-TV selection trials

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/test_tv_selection.py --trials 5 --max-steps 5
```

This diagnostic defaults to Qwen3-VL 8B Instruct on localhost:11435. Each trial
starts a fresh FloorPlan201 and positions the camera at a verified reachable TV
view, asserting that the TV is off and inventory empty. The VLM receives the
goal “Turn on the TV.” with the ordinary screenshot, feedback, schema, and legal
controls. Camera coordinates and a suggested action are not passed to the model.
Navigation controls remain available, but successful selection needs no movement.

Results are saved under `results/tv_selection_<UTC timestamp>/`, with a batch
summary, first-decision and eventual success counts, and before/after screenshots
plus decision traces for every trial. This isolates near-TV selection under
direct AI2-THOR rules; it does not test navigation or the benchmark remote rule.
See [progress.md](progress.md) for the actual measured results.

To start slightly farther away, add `--backoff 0.5`. This requests about 0.5 m
more TV distance than the baseline. The runner uses reachable-position metadata
to choose a free pose within 0.15 m of that requested distance, avoiding the
coffee table, and faces the camera toward the TV. `--backoff 0` preserves the
original pose; offsets from 0 to 3 m are accepted. Pose selection is scripted
setup, never passed to the VLM. Each trial records the actual setup command,
measured TV distance, and whether TV power control is initially eligible.
A farther pose can still be immediately interactable; consult that eligibility
flag rather than assuming the model needed to navigate.

### Require a calibrated number of forward steps

Calibrate a free start that rejects TV power-on until the requested number of
normal 0.25 m forward moves has been made. For three steps:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/calibrate_tv_step.py --steps 3
```

Use `--steps 1` for the earlier one-step setup. The calibrator supports 1–10,
searches candidate free poses, and fails if it cannot verify a suitable approach.
It verifies normal power-on rejection before each required step and success
only after the last one. This is scripted calibration, not model performance.

Pass the printed calibration directory's `result.json` to the trial runner:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/test_tv_selection.py --trials 5 --max-steps 5 \
  --step-fixture results/tv_step_calibration_<timestamp>/result.json
```

`--one-step-fixture` remains an alias for compatibility, and original one-step
fixtures are still accepted. Each model trial starts fresh at the verified
camera pose with the TV off and initially ineligible. The model receives only
the usual goal, screenshot, legal controls, and feedback; neither the number
of required moves nor the action sequence is supplied. Only initial placement
is assisted; every subsequent action must be chosen by the model.

The summary records the calibrated `required_forward_steps`, overall success,
and `exact_step_then_toggle_successes` (N forward actions followed immediately
by TV power-on, with all commands successful). Successful exact trajectories
save screenshots after each move and `middle.png` after the last walk.
Five decisions allow three moves plus power-on and one spare decision. A model
that turns away can exhaust that budget; a feasible calibration does not imply
model success. See [progress.md](progress.md) for the actual measured outcomes.

### Separate camera observations from eligible actions

Add `--scene-observations` to the selection runner to describe rendered objects
even when they are outside interaction range:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/test_tv_selection.py --trials 5 --max-steps 5 \
  --step-fixture results/tv_step_calibration_<timestamp>/result.json \
  --scene-observations
```

This optional assisted protocol uses simulator instance rendering to identify
objects in the current image, then supplies their type, interaction-range flag,
eligible actions, and relevant power/open/pickup states. For example, a rendered
TV can be reported as off and not currently interactable while TOGGLE_ON remains
absent from the eligible controls. Instance eligibility also depends on current
state and inventory; simulator feedback still determines whether execution works.

These labels and states come from simulator metadata, so this is an assisted
perception experiment. No object IDs, image/world coordinates, distances, route,
or required move count are supplied to the model. Off-screen objects are omitted.
Each decision saves `scene_observations.json`, separating model-visible labels
from raw rendering evidence. The summary records `scene_observations`; omitting
the flag preserves the existing protocol. See [progress.md](progress.md) for
results and comparison limits.

### Inspect saved images for target direction

To ask Qwen where a target appears and which movement it recommends, without
running the simulator:

```bash
uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/diagnose_direction.py --target Television \
  results/tv_selection_<timestamp>/trial_01/before.png \
  results/tv_selection_<timestamp>/trial_01/decision_01/after.png
```

Each image gets an independent request containing only the screenshot and the
same direction prompt. Results include LEFT/CENTER/RIGHT/NOT_VISIBLE/UNCERTAIN
and one suggested movement, with NONE requested for an absent or uncertain
target. This diagnostic has a separate output schema and never passes proposals
to the parser or simulator. It defaults to Qwen on port 11435; `--model` and
`--base-url` can override that. Exact prompts, image hashes, and raw responses
are saved under `results/direction_diagnostic_<timestamp>/`. Physical feasibility
and goal completion require a separate execution test.

### Locate the target before each live action

Add `--locate-before-action` to `scripts/test_tv_selection.py` or
`scripts/goal_tv.py` for a separate image-only target-location request before
every action decision. For a calibrated three-step trial:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/test_tv_selection.py --trials 5 --max-steps 5 \
  --step-fixture results/tv_step_calibration_<timestamp>/result.json \
  --locate-before-action
```

The locator reports LEFT/CENTER/RIGHT/NOT_VISIBLE/UNCERTAIN using the current
screenshot. The action model then receives the same screenshot, estimated
location, previous and last-seen locations, goal status, and eligible controls.
Feedback asks it to approach the target, recover a lost target, or perform the
goal interaction when available. The model still selects every action; no
fixed route, movement count, or direction-to-action mapping is supplied.

`household_agents/perception.py` provides the reusable locator and target memory.
Location is a VLM estimate, not a simulator label. The trial runner keeps this
option separate from `--scene-observations`; `--baseline` in the goal script also
cannot be combined with it. Normal output validation, instance resolution,
execution feedback, goal verification, and repetition handling still apply.

Each decision saves a nested `perception/` trace plus the action trace and
`target_tracking` feedback. Invalid perception prevents action selection and
execution, consumes one decision, and is retried with its validation error
within the existing decision/consecutive-failure limits. Runtime errors terminate
the episode. `--max-steps` still bounds action decisions; this protocol normally
uses two model requests per decision, so equal action budgets cost more inference.
All existing modes retain their default behavior when the option is omitted.
See [progress.md](progress.md) for measured results and limitations.

For compact action context, add `--action-prompt minimal` alongside
`--locate-before-action`. This sends the goal, eligible controls, movement
semantics, and a short target-location estimate. Last-seen recovery, the latest
error, and repetition feedback appear when needed; ordinary full tracking JSON
and successful-action history are omitted from this prompt. All traces remain
saved. `--action-prompt standard` is the default for existing comparisons.

For example, from the default room start:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/goal_tv.py --model qwen3-vl:8b-instruct \
  --base-url http://127.0.0.1:11435 --max-steps 40 \
  --locate-before-action --action-prompt minimal
```

### Compare action prompting and schema enforcement

To compare a saved live action request with a shorter prompt, both with and
without enforced output schema, pass one or more decision directories:

```bash
uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/compare_action_requests.py \
  results/tv_selection_<timestamp>/trial_01/decision_01 \
  results/tv_selection_<timestamp>/trial_01/decision_02
```

Each directory must contain `before.png`, `request.json`, `feedback.json`, and
`legal_choices.json`. The current prompt/schema case reproduces the saved
request; disabling enforcement removes only the API `format` field. Both prompt
variants request the same action/object JSON and retain the same factual state.
All raw answers are saved and validated without repair or retry; malformed
outputs are reported separately. This tool executes no simulator actions.
Results go to `results/action_request_comparison_<timestamp>/`. It defaults to
the Qwen endpoint on port 11435 and checks model/server identity against the
source batch when available. See [progress.md](progress.md) for findings.

### Diagnose action-context and runtime sensitivity

```bash
uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/diagnose_action_pipeline.py \
  results/tv_selection_<timestamp>/trial_01/decision_01 \
  results/tv_selection_<timestamp>/trial_01/decision_02
```

The saved decisions must contain the standard target-tracking action prompt.
This diagnostic probes prompt context, controls, goal wording, image omission,
simple direction/copy instructions, response contracts, sampling, and baseline
replays. It executes no actions. Add `--tracking-fields` for individual field
removal, or `--case '*_baseline'` to select named probes. Model/server overrides
support explicitly labeled comparisons with an installed model. Each run saves
its manifest, exact requests, source snapshot, model metadata, responses, and
validation under `results/action_pipeline_diagnosis_<timestamp>/`. See
[the detailed diagnosis](reports/action_pipeline_diagnosis_2026-11-08.md) for
controls, observed effects, and limitations.

## Evaluate different tasks and starting views

Run a small cross-task evaluation with the minimal action prompt and a separate
image-only target-location request before each action:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/evaluate_goals.py --max-steps 20
```

The default matrix contains 15 fresh-scene trials: TV power-on in FloorPlan201
and FloorPlan202, fridge OPEN/CLOSE and Mug PICKUP in FloorPlan1, each with a
nearby eligible start and two farther, angled starts where the goal interaction
is initially unavailable. Setup selects reachable camera positions with rendered
target pixels and establishes an unfinished initial object state using ordinary
simulator interactions. This is assisted initial placement; the model chooses
all subsequent movements and interactions. The rendered-instance labels and
setup coordinates are not supplied to the model. This uses direct AI2-THOR
interaction rules rather than the official benchmark's scenario rules.

Use repeatable `--case` and `--variant` options to select conditions, or
`--repeats 2` for additional fresh-scene trials. Cases are `tv201`, `tv202`,
`fridge_open`, `fridge_close`, and `mug_pickup`; variants are `near_center`,
`far_target_left`, and `far_target_right`. View names describe the intended
setup geometry; the visual locator can still misidentify target position.

For a separate evaluation from each room's original pose and object state,
with no setup actions, run:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/evaluate_goals.py --max-steps 20 --variant default_start \
  --case tv201 --case tv202 --case fridge_open --case mug_pickup
```

`default_start` reports a setup error rather than silently modifying state if
the requested goal is already complete. Fridge CLOSE is omitted here because
that room normally starts with the fridge closed.

Results are saved under `results/goal_evaluation_<timestamp>/`, including an
incremental summary, every setup attempt, source snapshots and hashes, exact
model/action traces, and before/after screenshots. Setup errors are reported
separately from model failures; failed episodes are retained without automatic
trial reruns. One default trial per condition is a diversity check, not a
statistical reliability estimate. See [progress.md](progress.md) and the
[varied-goal evaluation report](reports/goal_generalization_2026-11-12.md) for
outcomes and limitations.

## Use Qwen with the isolated newer Ollama

This workspace has Ollama **0.40.15** installed separately at
`/data/5pourghe/ollama-qwen/0.40.15/`, with Qwen3-VL 8B Instruct in
`/data/5pourghe/ollama-qwen/models/`. The shared Ollama 0.6.2 service remains on
port 11434; the isolated server uses **127.0.0.1:11435**. Installation/model files
are outside this repository and are not included in a clone.

The isolated server was started for the model trial. If it is not running,
start it in a terminal with:

```bash
bash scripts/serve_qwen.sh
```

The launcher runs in the foreground; keep that terminal open. It sets the
separate model directory, localhost port, one parallel request, one loaded model,
and disables cloud use. `OLLAMA_QWEN_DIR` can override the runtime root if the
same version is installed elsewhere. It does not install a system service or
replace the `ollama` command on PATH.

Check the isolated version and model list:

```bash
curl http://127.0.0.1:11435/api/version
OLLAMA_HOST=127.0.0.1:11435 \
  /data/5pourghe/ollama-qwen/0.40.15/bin/ollama list
```

Run the TV goal with Qwen and an explicit decision budget:

```bash
xvfb-run -a uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/goal_tv.py --model qwen3-vl:8b-instruct \
  --base-url http://127.0.0.1:11435 --max-steps 40
```

Only the server URL, model, and explicit decision cap change. The goal prompt,
controls, default scene/pose, and image/action history protocol are preserved.
Existing defaults still use the shared LLaVA server, so use both model and URL
options to select Qwen. Results and comparison limitations are in
[progress.md](progress.md).

For installation on another machine, follow the
[official manual installation instructions](https://docs.ollama.com/linux) and
[versioned release/checksums](https://github.com/ollama/ollama/releases/tag/v0.40.15),
extract into a separate directory, then pull the model against the new server:

```bash
OLLAMA_HOST=127.0.0.1:11435 \
  /data/5pourghe/ollama-qwen/0.40.15/bin/ollama pull qwen3-vl:8b-instruct
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

To run Qwen through the unchanged official benchmark, use the isolated endpoint
and a model alias with an explicit context allocation. The default 4K allocation
is too small for its prompt. See the [official sanity report](reports/official_sanity_qwen_2026-11-12.md)
for alias creation, a separate-output command, and evaluation evidence.

## Scope

The shared object engine supports bounded OPEN/CLOSE/PICKUP/TOGGLE interactions
and object-state goals. The interaction/procedure CLIs expose OPEN/CLOSE/PICKUP;
ordered caller-supplied procedures reuse that engine with scripted initial camera
setup. The separate goal-only episode lets the model select basic navigation
and power interactions from the initial scene, without a supplied plan. Reliable
autonomous planning has not been established. PUT and SLICE remain unsupported.
The official benchmark remains external and unchanged. No script trains a model.
Generated screenshots and results remain local and ignored by Git. See
[progress.md](progress.md) for results, known issues, and investigation reports.
