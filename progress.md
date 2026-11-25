# Progress log

This is the ongoing record of project work, bugs, attempted fixes, results, and
remaining issues. Dates use Europe/Berlin time; timestamped artifact directory
names use UTC. Earlier work was reconstructed on November 8, 2026 from repository
history, saved results, the investigation report, and this work session. Where
an exact original date is unavailable, the entry says so.

## By November 1, 2026 — Initial project and environment

- Established `vlm-household-agents` with AI2-THOR, local Ollama, and LLaVA 7B.
  AsgardBench is a sibling external dependency, pinned in
  [asgardbench-commit.txt](asgardbench-commit.txt) to
  `4d38d380362d767893611fc160dc78665d1356b8`.
- Added `scripts/test_environment.py`: loads FloorPlan1, captures the initial
  image, rotates right, and saves the second image. Rendering and rotation worked.
- Added `scripts/test_vision.py`: sends the initial screenshot to LLaVA through
  Ollama's OpenAI-compatible endpoint. Image inference worked.
- Ran the two-task AsgardBench sanity check: **0/2 successes**. Model responses
  described the scene without usable actions. The exact initial run date was not
  established in this documentation update. Benchmark output is under the
  external `../AsgardBench/Test/magt_benchmark_sanity/` directory.
- Initial project commit: `e81d504`. Generated images, model files, environments,
  secrets, and result directories were excluded from Git.
- No model training or autonomous task completion was demonstrated.

## November 1, 2026 — Message placement and context investigation

- Compared the same full prompt as separate system/user messages (A) and
  combined user text (B), using the same screenshot and task, “Open the fridge.”
  Both returned descriptions without actions. Merely combining messages did
  not solve the full-prompt failure.
- Tested contexts of 2,048 and 16,384 with an explicit native output limit of
  256 tokens. At 2,048, responses completed scene descriptions. At 16,384,
  responses began structured task-related output but hit the output limit before
  reaching an Action line.
- Found a version compatibility problem: Ollama 0.6.2's OpenAI adapter uses
  `max_tokens`, not the previously requested `max_completion_tokens`. Switched
  diagnostics to native `/api/chat` with explicit `num_ctx` and `num_predict`.
- Source inspection identified ways earlier text can be dropped when message
  layouts exceed context. Runtime token-retention traces were inaccessible;
  context-dependent behavior is observed, but exact dropped input is unconfirmed.
- Initial runner inspection through `/proc` was permission-restricted. Later
  `ps` captures verified configured context allocations. Journal access remained
  restricted; absence of visible log entries was not treated as proof of no
  truncation. Shared-service snapshots cannot exclude intervening workloads.
- Artifacts (local, ignored):
  `results/message_placement_20261101T080400_762672Z/` and
  `results/context_control_20261101T082120_017284Z/`.

## November 1, 2026 — Action-output workaround

- Ran six additional context/layout cases at a 1,024-token output allowance,
  followed by one explicit output-contract case. Requests were single attempts
  with no automatic retries.
- More output tokens let high-context full-format responses reach Action lines,
  but names such as `Refrigerator` and `Knife` were invalid for that diagnostic's
  legal vocabulary (`Fridge`). Another response used invalid action syntax,
  `Action: Approach the fridge`. The unchanged parser correctly rejected them.
- A final compact output contract, full prompt, combined text/image message,
  native context 16,384, and `num_predict=1024` produced
  `Action: OPEN Fridge`. The unchanged AsgardBench parser accepted it.
- This established one formatting/action-choice sample. No returned action was
  executed in this investigation, and the official benchmark was not rerun.
  The restricted object list was diagnostic-specific rather than simulator-derived.
- Artifacts (local, ignored):
  `results/action_output_20261101T082542_286389Z/` and
  `results/action_output_20261101T082642_535422Z/`.
- Full methods, seven-case table, source references, and evidence limitations:
  [investigation report](reports/ollama_llava_action_diagnostic_2026-11-01.md).

## November 5, 2026 — Scripted pickup smoke test

- Added `scripts/test_pickup.py`, which searches nearby views for a visible,
  pickupable object, attempts pickup, and checks object state and inventory.
- First saved attempt failed during initialization: `rotateStepDegrees=45`
  was incompatible with `snapToGrid=True`.
- Corrected the rotation configuration to 90 degrees. The next attempt picked
  up a CreditCard in FloorPlan1 on its first pickup action. Metadata confirmed
  `isPickedUp=True` and the object appeared in inventory.
- This was a scripted simulator test without model inference.
- Artifacts (local, ignored): failed setup in
  `results/pickup_20261105T123634_564003Z/`; successful pickup and before/after
  images in `results/pickup_20261105T123650_912800Z/`.

## November 8, 2026 — Repository cleanup and GitHub publication

- Removed the three one-off diagnostic scripts:
  `diagnose_message_placement.py`, `diagnose_context_length.py`, and
  `diagnose_action_output.py`. The later scripts depended on local, ignored
  experiment artifacts and were unsuitable as fresh-clone entry points.
- Kept rendering, vision, and pickup smoke tests, updated the README, and
  preserved diagnostic findings in the archived investigation report.
- Validation: retained Python scripts passed syntax checks, README local links
  resolved, and `git diff --check` passed. No new inference was needed for cleanup.
- Shell HTTPS push failed because no GitHub credentials were configured. Used
  the connected GitHub app to publish equivalent committed contents to `master`:
  [40358b9](https://github.com/Ali-Pourgheisari/vlm-household-agents/commit/40358b973ae4ff6e25e325424a57a6eee66e4011).
- Local commit `5fe5761` and published commit `40358b9` have the same tree
  (`236651b8dc41bb13e0ffaa7dd2d70391d2720272`) but different commit IDs. A later
  shell fetch also failed for missing credentials; branch history synchronization
  remains unresolved. Do not force-push or overwrite remote work to resolve it.

## November 8, 2026 — Live VLM → parser → environment fridge interaction

- Added [scripts/interact_fridge.py](scripts/interact_fridge.py) for a single-step
  interaction: prepare a fridge view, capture `before.png`, send its exact bytes
  and task to LLaVA, parse the actual response, execute the parsed action, and
  capture `after.png` plus result metadata.
- Setup uses reachable positions and scripted camera teleportation to face a
  nearby closed fridge. This is setup assistance, not model-selected navigation.
- Legal object names come from visible, openable simulator metadata. The
  unchanged AsgardBench parser returns action/object names. A bridge maps
  `OPEN`/`CLOSE` to `OpenObject`/`CloseObject` and resolves the nearest visible
  matching object ID. Interactions do not use `forceAction`.

### Attempt 1 — Rejected incomplete output

- Short prompt, native context 16,384, output allowance 256, temperature 0.
- Actual model response: `Action: OPEN`, missing the object name. Generation
  ended normally, so this was not an output-limit failure.
- Parser returned `FAIL: Action content not found`. No model-selected simulator
  action was executed; the fridge remained closed. Before/after images and the
  failure record were saved.
- Artifact directory: `results/fridge_interaction_20261108T105623_945517Z/`.

### Attempt 2 — Successful model-selected execution

- Changed to the full benchmark prompt plus a final compact output contract
  explicitly requiring both action and object. Increased output allowance to
  1,024; retained context 16,384, temperature 0, and top_p 1.
- Actual response: `Action: OPEN Fridge`; normal stop after 8 completion tokens.
  Reported prompt usage: 6,816 tokens.
- Parser accepted `OPEN` and `Fridge`. Bridge sent `OpenObject` for
  `Fridge|-02.10|+00.00|+01.07` to AI2-THOR.
- Simulator returned success with no error; metadata changed from `isOpen=false`
  to `isOpen=true`. Screenshots were visually inspected and show closed/open
  fridge views from the same camera.
- Artifact directory: `results/fridge_interaction_20261108T105659_239408Z/`.
  Contains `before.png`, `after.png`, `prompt.txt`, sanitized `request.json`,
  `raw_response.json`, `response.txt`, `visible_objects.json`,
  `parsed_action.json`, `simulator_command.json`, and `result.json`.
- Validation: live end-to-end success, command-line help check, and
  `git diff --check`. One model request per invocation; no automatic retries or
  replacement of invalid responses.
- Outcome: **two attempts with different prompts/settings, one successful
  execution**. This is not a measured 50% success rate under fixed conditions.
  A full benchmark rerun, autonomous navigation, and multi-step task completion
  remain unverified. Script and README changes were not committed or published
  during this interaction task.

## November 8, 2026 — Reliability discussion (proposed work only)

- Agreed that one successful run does not establish reliability and no prompt
  or model guarantees all actions will succeed.
- Recommended schema-constrained output with mandatory action/object fields,
  validation before conversion to the existing parser format, bounded recovery,
  and simulator feedback after execution. Compatibility with the installed
  Ollama version still needs testing; no structured-output change was implemented.
- Recommended repeated tests across positions, scenes, and open/closed states,
  measuring first-attempt success separately from success after retries and
  separating parser failures from simulator failures.
- Discussed comparing a newer vision model under identical conditions after
  improving the interface. Qwen3-VL 8B was a candidate; its published Ollama
  requirement was 0.12.7+, beyond the investigation's 0.6.2 installation. No model
  was downloaded, upgraded, benchmarked, or substituted.
- Reference documentation consulted:
  [Ollama output format](https://github.com/ollama/ollama/blob/main/docs/api.md)
  and [Qwen3-VL 8B requirements](https://registry.ollama.com/library/qwen3-vl%3A8b).

## November 8, 2026 — Consolidated progress documentation

- Created this `progress.md` (corrected from the initially requested spelling
  `progres.md`) and reconstructed earlier work, including failed attempts,
  fixes, results, evidence limits, publication issues, and proposed next steps.
- Removed the Current progress section and dated experiment history from
  README.md, replacing them with a link here. README retains setup, usage, and
  scope. Preserved the detailed archived report as supporting evidence.
- Added [AGENTS.md](AGENTS.md) requiring future project work to update this log,
  including bugs, problems, attempted fixes, validation, and remaining work.
- Validation: checked Markdown local links, confirmed the README no longer has
  a Current progress section, checked the required log/instruction files exist,
  and ran `git diff --check`. No simulator or inference rerun was needed for this
  documentation change. This update has not been committed or published.

## November 8, 2026 — Constrained output and bounded recovery

- Updated `scripts/interact_fridge.py` to send an Ollama JSON schema requiring
  exactly `action` and `object`, with enums for OPEN/CLOSE and visible, openable
  simulator object types. The installed server accepted schema-constrained
  generation in the live run; no service/model upgrade was needed.
- Added application validation for malformed JSON, missing/extra/duplicate fields,
  incorrect types, unsupported actions, unknown objects, and incomplete generation.
  Only validated choices become `Action: ACTION OBJECT` for the unchanged parser.
  Missing values are not filled in and model choices are not substituted.
- Added `--max-retries` (default 2, range 0–5): one initial request plus a shared
  budget of extra attempts for validation, simulator, state, or goal failures.
  Every retry includes the actual previous error/response/command and a fresh
  screenshot. Current metadata supplies object choices on each attempt.
- Reject already-open/closed target actions before execution. After executing,
  check `lastActionSuccess`, simulator error, the commanded object's resulting
  open state, and the task goal (fridge open). A successful API/action flag alone
  does not establish task success. Physics is not bypassed with forceAction.
- Transport/HTTP/runtime failures terminate without automatic retries. Failed
  validation never reaches the simulator. Stop immediately on task success and
  fail after the configured budget if the task remains incomplete.
- Added per-attempt artifact directories and preserved root before/final-after
  images. Every attempt records its outcome, failure stage, model usage, and
  feedback. Summary flags separate first-attempt success from recovered success.
- Live validation: native schema request returned
  `{"action": "OPEN", "object": "Fridge"}` on attempt 1 of a maximum 3;
  unchanged parser accepted it, OpenObject succeeded, and fridge metadata changed
  from closed to open. Reported usage: 6,808 prompt tokens, 15 completion tokens.
  `first_attempt_success=true`, `recovered=false`.
- Live artifacts (local, ignored):
  `results/fridge_interaction_20261108T114737_252354Z/`, including
  `attempt_01/request.json`, raw response, parsed action, command, before/after
  images, and results. No live retry was necessary in this run.
- Added `tests/test_interact_fridge.py`: eight offline tests cover malformed,
  missing, duplicate, extra, invalid and truncated output; recovery after missing
  fields; simulator rejection feedback; budget exhaustion without execution;
  immediate success; disabled retries/no-op rejection; false-positive simulator
  success without state change; and terminal connection failure. These tests
  use scripted responses and a fake controller, not model reliability trials.
- Validation: all eight offline tests passed; live simulator/VLM first attempt
  succeeded; CLI help and `git diff --check` passed. README documents the schema,
  recovery controls, artifact layout, and test command. Changes remain local,
  uncommitted, and unpublished.
- Remaining limitation: constrained formatting cannot guarantee visual judgment,
  feasible actions, or eventual recovery. No live obstacle-recovery trial or
  repeated model reliability evaluation was performed. There is no navigation
  fallback, schema-training change, or official benchmark rerun.

## November 8, 2026 — Reusable model, executor, and task components

- Problem: model requests, validation, execution, and the fridge goal were coupled
  inside `scripts/interact_fridge.py`. Other openable objects could be acted on,
  but success was always checked against the fridge. PICKUP had no execution
  or goal support in the interaction loop.
- Split the implementation into three responsibilities:
  - `household_agents/model.py`: Ollama image requests, full benchmark prompt,
    constrained JSON, exact output validation, and unchanged-parser conversion.
  - `household_agents/executor.py`: capability/state-based eligible objects,
    exact instance resolution, OPEN/CLOSE/PICKUP commands, simulator errors,
    resulting open state, and pickup state plus inventory verification.
  - `household_agents/tasks.py`: `ObjectTask` defines operation, target type,
    optional exact instance, allowed actions, and goal completion independently
    of the model and action executor.
- `household_agents/engine.py` now handles orchestration, one shared bounded retry
  budget, actual error feedback, refreshed screenshots/choices, per-attempt
  artifacts, and distinct first-attempt/recovered/already-satisfied results.
  Already-completed goals skip inference and execution.
- `scripts/interact.py` provides generic `--action OPEN|CLOSE|PICKUP --object TYPE`
  with optional `--object-id`, scene/model/retry controls, and `--no-setup`.
  `scripts/interact_fridge.py` is a thin OPEN Fridge example using the same CLI
  wiring; no model, parser, simulator action, or goal logic remains in that file.
- Optional demo setup lives in `household_agents/setup.py`. It places the camera
  near the target and adjusts initial open state for OPEN/CLOSE demonstrations;
  those setup actions are logged separately. Core engine calls on an existing
  controller do not move the camera or reset target state.
- Legal choices now respect capabilities, visibility, open/closed state, and
  hand occupancy. The schema constrains action/object enums; application
  validation checks pair compatibility. A bound target ID cannot silently be
  replaced by a nearer instance of the same type. A successful action on another
  object does not complete the target goal.
- Artifact layout remains root before/final-after screenshots and `attempt_XX/`
  directories. Generic CLI uses `results/interaction_<UTC timestamp>/`. Target
  state summaries are now lists, supporting type-based tasks; later results
  also record camera, allowed actions, and inventory evidence.
- Renamed/generalized tests as `tests/test_interaction.py`: 16 offline tests
  passed, preserving previous recovery cases and adding cabinet OPEN/CLOSE,
  Apple PICKUP/inventory, capability/state/hand filters, exact instance selection,
  already-satisfied goals, cross-action pair rejection, and wrong-object goals.
  Fake-controller tests are software checks, not model reliability measurements.
- Live checks used LLaVA 7B and real AI2-THOR after scripted camera setup. Each
  succeeded on its first model request, with normal generation stop and actual
  object-state verification:

  | Task | Model choice | Simulator command | Local artifact directory |
  | --- | --- | --- | --- |
  | Open Fridge | OPEN Fridge | OpenObject | `results/interaction_20261108T120052_248799Z/` |
  | Open Cabinet | OPEN Cabinet | OpenObject | `results/interaction_20261108T120116_678355Z/` |
  | Pick up CreditCard | PICKUP CreditCard | PickupObject | `results/interaction_20261108T120137_077260Z/` |
  | Close Cabinet | CLOSE Cabinet | CloseObject | `results/interaction_20261108T120212_442770Z/` |

- Pickup was verified using both `isPickedUp` and inventory membership. For CLOSE
  Cabinet, setup first opened the cabinet and recorded that scripted action;
  the subsequent CLOSE was selected by the model. Screenshots and response/action
  traces were saved for every live run. These four samples do not establish
  reliability across scenes, repetitions, or physical failure cases.
- README now documents the three responsibilities, generic CLI examples,
  direct Python reuse, instance semantics, setup assistance, recovery, and tests.
  Both CLI help checks, all 16 tests, local documentation links, source syntax,
  and `git diff --check` passed. Changes remain local, uncommitted, and unpublished.
- Remaining scope: OPEN/CLOSE/PICKUP object-state goals only. No navigation,
  general task planner, PUT/SLICE/TOGGLE support, model upgrade, training, or
  official benchmark rerun. Occluded/unreachable targets can fail demo setup;
  physically impossible commands can still fail despite valid formatting.

## November 8, 2026 — Publish the reusable interaction engine

- Reviewed pending work and grouped the shared engine, model/executor/task
  separation, OPEN/CLOSE/PICKUP entry points, recovery tests, README, and progress
  logging instructions into one coherent commit for GitHub `master`.
- Re-ran the existing 16 offline regression tests before publication; all passed.
  Previously recorded live results remain the evidence for simulator/model
  behavior; no additional inference was needed for publication.
- Used the connected GitHub app because shell HTTPS credentials remain
  unavailable. Resolved the earlier local/remote base mismatch by importing the
  exact GitHub commit object, verifying its SHA and matching tree, and aligning
  the local base without changing working files. The former local cleanup
  commit is preserved under `refs/codex/pre-sync-cleanup`.
- Publication uses the existing remote head as its parent and a non-forced ref
  update with an expected-head check. The published update is identified by the
  Git commit containing this entry; no generated screenshots, result directories,
  model files, virtual environments, or secrets are included.
- Source syntax, local documentation links, and whitespace checks passed.
  The intended final state is matching local/GitHub commit and tree with a clean
  working copy. Shell authentication remains a separate unresolved setup issue.

## November 8, 2026 — Open then close the fridge in one continuing scene

- Added reusable `household_agents/procedure.py` orchestration for ordered
  `ObjectTask` steps using the existing model interface, executor, goal checks,
  retry policy, and per-attempt evidence. `scripts/procedure.py` and
  `household_agents/procedure_cli.py` provide an OPEN/CLOSE Fridge example with
  action sequence, object/instance, scene, model, and retry arguments.
- Demo camera and initial-state setup runs once before the procedure. The exact
  target object ID, simulator controller, and camera persist across steps. No
  scripted open/close action, reset, or repositioning occurs between steps.
- Each step sends its current screenshot to the VLM and executes only validated
  and parsed model output. Later steps run only after the previous goal succeeds.
  Retries are bounded per step; exhausting a budget stops the procedure.
- Added before/middle/after root screenshots, per-step checkpoints, target state
  and camera metadata, a procedure summary, and full nested step/attempt traces.
  On failure, after.png is labeled the final observed state, not proof of success.
- Added three offline procedure tests: same-instance OPEN→CLOSE continuity and
  closed/open/closed checkpoints, first-step failure stopping before closing,
  and second-step failure preserving the open middle/final state. All 19 tests
  (16 existing plus 3 new) passed.
- Live run: `scripts/procedure.py --actions OPEN CLOSE --object Fridge` on
  FloorPlan1 with LLaVA 7B. Both steps succeeded on their first attempt, with
  two model requests total and no recovery required:
  1. JSON choice OPEN Fridge → parser OPEN Fridge → OpenObject succeeded;
     exact fridge metadata changed from closed to open.
  2. A fresh image of that open fridge was sent to the model. JSON choice
     CLOSE Fridge → parser CLOSE Fridge → CloseObject succeeded; metadata
     changed back to closed.
- Target ID for both commands: `Fridge|-02.10|+00.00|+01.07`. All checkpoint
  camera poses matched. Visual inspection confirmed closed/open/closed images.
  No errors or simulator rejections occurred in this live procedure.
- Artifacts (local, ignored): `results/procedure_20261108T134329_811968Z/` with
  `before.png`, `middle.png`, `after.png`, `checkpoint_01.png`,
  `checkpoint_02.png`, `result.json`, and `step_01/` / `step_02/` traces.
- README documents the command, artifact layout, per-step retry policy, and
  supplied-sequence limitation. CLI help, source syntax, documentation links,
  whitespace, same-ID/state/camera checks, and all 19 offline tests passed.
  Changes remain local, uncommitted, and unpublished.
- Scope: this is a verified two-step caller-supplied procedure with model-selected
  interactions, not independent multi-step planning or a reliability benchmark.

## November 8, 2026 — Goal-only TV experiment (did not reach the goal)

- Request: give the model “Turn on the TV” without a supplied action sequence,
  to observe whether it can decide how to achieve the goal.
- Added `household_agents/episode.py` and `scripts/goal_tv.py`: the model sees
  only the current image, goal, JSON/control interface, eligible object names,
  and its own observed action/outcome history. No benchmark examples, suggested
  sequence, target coordinates, route hints, scripted search, camera setup,
  teleports, or object-state preparation are used.
- Added explicit MOVE_AHEAD/MOVE_BACK (0.25 m), ROTATE_LEFT/ROTATE_RIGHT
  (45 degrees), and LOOK_UP/LOOK_DOWN (30 degrees) controls in
  `household_agents/navigation.py`. Navigation uses a local explicit adapter
  because the unchanged AsgardBench parser has no navigation actions. Object
  actions still use that external parser, and trace metadata labels the adapter.
- Extended reusable tasks/executor with TOGGLE_ON/TOGGLE_OFF, capability/state
  checks, actual power-state verification, and optional literal goal text.
  Added a configurable model prompt builder so this experiment does not receive
  the full benchmark prompt or action examples. Existing object demos retain
  their original prompt builder.
- The episode has a total decision limit (default 12) separate from a consecutive
  failure limit (3). Valid successful navigation continues rather than counting
  as a failed goal attempt. Each decision refreshes the image and controls.
  Episode stops at verified goal completion or a limit and preserves failures.
- One live run in FloorPlan201, starting at the default camera/position, with
  LLaVA 7B and literal goal `Turn on the TV.`. No setup actions or hidden helper
  commands were executed. **Goal not achieved** after 12 model decisions:
  1–6 MOVE_AHEAD; 7 ROTATE_LEFT; 8 MOVE_AHEAD; 9 LOOK_UP;
  10 ROTATE_LEFT; 11–12 MOVE_AHEAD.
- All 12 responses were valid constrained JSON and all simulator actions reported
  success. There were no parser, schema, or execution failures. The model never
  selected a power action; it ended facing a wall. This distinguishes successful
  execution of chosen moves from successful goal-directed behavior.
- The TV was rendered in the initial image but outside the simulator's 1.5 m
  interaction visibility range. Saved metadata reported distance about 5.03 m
  initially and 3.86 m finally, with `visible=false` and `isToggled=false` at both
  endpoints. `Television` was never eligible in any saved decision's control list,
  so TOGGLE_ON Television was not available in this episode. These distances and
  off-screen target metadata were used for evaluation/logging only and were not
  supplied to the model. Do not interpret this as testing power-action selection
  when a TV is already reachable.
- Stop reason: `decision_limit`; `goal_success=false`; CLI exited with status 2.
  The run was not restarted with hints or a modified prompt to force a success.
  Twelve decisions may be insufficient; this single bounded run does not prove
  the model can never achieve the goal or establish why navigation choices failed.
- Artifacts (local, ignored): `results/tv_goal_20261108T135314_929489Z/` contains
  before/after images and 12 `decision_XX/` traces with the exact prompt, schema,
  raw response, parsed action, simulator command, feedback, and camera poses.
  Before/after images and the action/control traces were inspected.
- Added seven offline tests in `tests/test_episode.py`: navigation then power
  selection with refreshed controls, decision-limit failure despite valid moves,
  consecutive-invalid-output stopping, power flag/state mismatch, already-on goal
  handling, navigation adapter validation, and prompt content without a plan.
  Fake-controller power success is not a live TV success claim.
- Validation: all 26 offline tests passed (19 previous plus 7 new); CLI help,
  source syntax, local documentation links, and `git diff --check` passed.
  README documents the controls, range restriction, prompt, adapters, limits,
  and evidence. Changes remain local, uncommitted, and unpublished.

## November 8, 2026 — Hardware and model-comparison feasibility

- Checked the available GPU and installed serving stack before recommending a
  stronger-model comparison: NVIDIA GeForce RTX 3080 Ti, 12,288 MiB total VRAM
  (11,874 MiB free at the snapshot); Ollama 0.6.2; only llava:7b installed
  (4.7 GB model file). Free VRAM is a momentary measurement, not a reservation.
- Reviewed the official Qwen3-VL 8B Instruct model page:
  https://ollama.com/library/qwen3-vl:8b-instruct . It requires Ollama 0.12.7+.
  A quantized 8B candidate is plausible for this GPU, but actual fit depends on
  quantization, image/context memory, and concurrent simulator/other workloads;
  it has not been measured here.
- Recommended comparing the newer vision model against LLaVA using the same
  goal-only prompt, initial scene/position, controls, and decision budget, then
  repeating across scenes. Better visual/action reasoning is a hypothesis to
  test, not an observed TV success or guarantee.
- No model download, service upgrade, configuration change, or inference run was
  performed. An isolated newer server/port would preserve the shared installation
  if a model trial is authorized later. This is feasibility research only.

## November 8, 2026 — Isolated Ollama upgrade and Qwen trial (setup)

- User authorized installing a newer Ollama and using Qwen for the TV experiment.
  Chose an isolated installation rather than changing the shared service.
- Downloaded official Ollama 0.40.15 (latest release returned by GitHub at setup)
  to `/data/5pourghe/ollama-qwen/0.40.15/`; verified release archive SHA-256
  `628c018404a4206493efd38e46251c154ede5141b8b8dc85c659b3b027c47379`
  against the official release checksum list before extraction.
- Added `scripts/serve_qwen.sh`: foreground local-only server on 127.0.0.1:11435,
  separate model store `/data/5pourghe/ollama-qwen/models`, one parallel request,
  one loaded model, cloud disabled. Shared Ollama 0.6.2 on 11434 is unchanged.
- Started the isolated server and verified `/api/version` reports 0.40.15.
  Runtime logs/PID/version are outside the repository under
  `/data/5pourghe/ollama-qwen/`; the server was launched as a detached process.
- Added `--base-url` to `scripts/goal_tv.py`; its previous default is retained.
  Preparing qwen3-vl:8b-instruct for the same goal prompt, initial scene, controls,
  context/output options, and 12-decision cap as the LLaVA trial.
- At this setup entry the model download and inference comparison were pending;
  the verified outcomes are recorded in the following entry.

## November 8, 2026 — Qwen installed and tested; TV goal still incomplete

- Successfully downloaded and verified `qwen3-vl:8b-instruct`, Q4_K_M, 8.2B,
  6,190,971,795 bytes including the image projector. Model digest:
  `70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb`.
- Confirmed simultaneous server versions: shared 11434 reports 0.6.2; isolated
  11435 reports 0.40.15. The isolated server is a detached local process, not an
  auto-start system service. `scripts/serve_qwen.sh` can start it after shutdown.
- Qwen loaded all 37 layers onto the GPU. Runtime snapshot reported context
  16,384 and 7,863,753,768 bytes model VRAM allocation; nvidia-smi showed about
  9,214 MiB total GPU usage during inference, including other allocations.
  Initial model loading was slower than subsequent image/action requests.
- Kept the original goal-only prompt, available controls, FloorPlan201 default
  pose, model options (temperature 0, top_p 1, context 16,384, output limit 1,024),
  and visibility settings. No route hints, target positioning, or subgoals were
  supplied. Added only model/server selection via the new `--base-url` argument.
- Matched-cap Qwen run: **failed to reach TV goal in 12 decisions**, all valid
  and successfully executed. Choices: 5 MOVE_AHEAD, 3 ROTATE_RIGHT, 2 LOOK_UP,
  2 LOOK_DOWN. TV remained off, reported final distance about 4.02 m.
  Artifacts: `results/tv_goal_20261108T140129_658439Z/`.
- Noticed a budget problem in the earlier experiment design: the initial TV
  distance was about 5.03 m, each translation covers 0.25 m, and 12 translations
  cover only 3 m before allowing any rotations or a power action. This makes
  the 12-decision cap a poor test of task completion. This distance estimate is
  not a formal shortest-path/visibility proof: observed visible objects can
  report center distances beyond the configured visibility threshold.
- Ran a separately labeled **40-decision Qwen trial**, starting fresh without
  changing the prompt or supplying hints. It also failed: after 6 MOVE_AHEAD
  and 2 ROTATE_RIGHT actions, decisions 9–40 alternated TOGGLE_ON Laptop and
  TOGGLE_OFF Laptop (16 of each). The selected laptop toggles all executed and
  passed power-state checks, but the Television remained off and never became
  eligible. Reported final TV distance about 4.11 m. Stop reason `decision_limit`,
  exit status 2. No parser/schema/command failures occurred.
  Artifacts: `results/tv_goal_20261108T140244_433022Z/`.
- This exposes a goal-selection/repetition problem beyond formatting: valid
  actions on the wrong device do not satisfy the goal, and the current loop
  only stops such successful-but-unproductive repetition at its total budget.
  Did not inject hints, filter away the laptop, or add a loop-avoidance policy
  during these runs. A stronger model alone did not solve this experiment.
- Comparison limits: the 12-step initial literal prompts and initial camera
  metadata match the LLaVA baseline exactly. Rendered image hashes differ across
  fresh launches; mean absolute RGB pixel differences were approximately
  0.221/255 (Qwen 12) and 0.222/255 (Qwen 40) against the baseline. Model and
  server version both changed, and the 40-step run changes budget as well.
  These are individual exploratory samples, not a statistically controlled
  model ranking. The two Qwen trajectories diverged despite temperature 0;
  exact deterministic replay is not established.
- Saved runtime/model provenance with both Qwen runs and outside the repository
  in `/data/5pourghe/ollama-qwen/installation.json`, `models.json`, `running.json`,
  and `version.json`. Server log/PID are in that runtime directory. Before/after
  images and saved action traces were inspected; the long run ends facing the
  laptop. Installation archives, models, keys, and logs are not committed.
- README documents the isolated install/version/port, foreground launcher,
  model listing/pull commands, and exact Qwen TV invocation. All 26 existing
  tests passed; CLI help, launcher shell syntax, source syntax, local links,
  and `git diff --check` passed. Shared service and model store remain unchanged.
  New project changes remain local, uncommitted, and unpublished.

## November 8, 2026 — Qwen3-VL variants and GPU-memory guidance

- Reviewed the current official Ollama Qwen3-VL catalog and tags:
  https://ollama.com/library/qwen3-vl/tags . Relevant vision sizes are 2B, 4B,
  8B, 30B-A3B, 32B, and 235B, with Instruct/Thinking and Q4_K_M/Q8_0/BF16
  variants. This is the Qwen3-VL family used here, not all Qwen model families.
- Published Q4 package sizes are approximately 1.9, 3.3, 6.2, 20, 21, and
  143 GB respectively. These are download sizes, not guaranteed runtime VRAM.
- User-facing GPU capacity ranges are planning estimates for single-request
  inference with moderate context/images, not measured minima or full-256K
  context requirements. Our only measured model remains 8B Q4 at context 16,384:
  about 7.86 GB model VRAM allocation and about 9.0 GiB total GPU usage at the
  recorded snapshot. The existing 12 GiB RTX 3080 Ti ran it successfully.
- Q8/BF16 use more weight memory (official 8B package sizes: 9.9/18 GB).
  Larger context, more/larger images, concurrent requests, and simulator GPU
  usage increase memory needs. Thinking can generate longer sequences; it does
  not imply a smaller model or establish better TV-task success.
- No additional models were downloaded, loaded, benchmarked, or changed during
  this research; no GPU purchase or service change was made.

## November 8, 2026 — Goal feedback and state-aware repetition recovery

- Problem: Qwen issued valid, successful actions on the wrong device and looped
  without a clear goal-status signal or a bound on successful-but-unproductive
  action cycles. User authorized goal feedback and repetition detection.
- Enhanced `household_agents/episode.py` feedback with the literal goal, an
  explicit completion flag/message after every decision, and observed state of
  the acted-on object. A successful laptop interaction can no longer be reported
  to the model without also stating that the TV goal remains incomplete.
- Feedback omits hidden target positions/distances and coordinate-bearing object
  IDs; failed-command feedback is sanitized too. No route, replacement action,
  scripted task decomposition, or target positioning is supplied.
- Added `household_agents/repetition.py`: detects identical short action cycles
  of length 1–4 repeated twice, with matching pose/relevant-object/inventory
  signatures at cycle boundaries. Rounded pose and signed-zero normalization
  avoid tiny numerical differences hiding a loop. Missing pose disables state-
  based detection; repeated forward moves that change position are not flagged.
- On detection while the goal is incomplete, send a specific cycle warning on
  the next request. A model choice that would continue that cycle is rejected
  before execution. Default two such rejected choices stop with repetition_limit;
  zero stops immediately on detection. A different successful action clears the
  active warning, with a recovery decision recorded. This is local-cycle recovery,
  not a claim of task progress or completion. Later cycles remain detectable.
- Added `--max-repetition-retries` (0–5, default 2) and `--baseline` to the TV
  runner. Baseline restores the old history-only feedback and disables repetition
  intervention. Request budget and separate consecutive-failure bound remain.
  Artifacts now include per-decision feedback.json, goal_status, action tokens,
  and episode repetition_events including recoveries/rejections/stopping.
- Added nine offline tests in `tests/test_repetition.py`: laptop-cycle detection
  and bounded non-execution of repeated choices; alternate-action recovery;
  actual object/goal feedback; baseline compatibility; zero recovery budget;
  sustained useful forward movement; missing pose; numeric noise/signed zero;
  and successful-goal handling. All 35 tests passed (26 previous plus 9 new).
- New live Qwen3-VL 8B Instruct run on isolated Ollama 0.40.15, same FloorPlan201
  default setup, 40-decision cap, no route hints or scripted positioning:
  **TV goal still not achieved**; all 40 responses/actions were valid and reported
  simulator success; final stop reason decision_limit.
- Five repeated LOOK_DOWN/LOOK_UP cycles were detected at decisions 19, 24, 29,
  34, and 39. After every warning, the model chose MOVE_AHEAD at decisions 20,
  25, 30, 35, and 40. Thus five local cycles were exited without a loop-continuing
  choice being rejected in this live run. The blocked-choice/stop path was
  verified offline with scripted model responses, not observed live here.
- Final TV reported distance about 2.24 m, versus about 4.11 m in the previous
  baseline Qwen 40-decision run. TV remained ineligible/off. This new run improved
  the observed distance and avoided the prior laptop loop, but repeatedly formed
  new look cycles; it does not establish reliable navigation or causality from
  one exploratory comparison. The prompt changed and rendering can vary.
- Artifacts (local, ignored): `results/tv_goal_20261108T142204_537547Z/`, with
  before/after screenshots and 40 decision traces. The executed process used
  the first detector implementation; signed-zero normalization and explicit
  per-cycle rejection-count bookkeeping were finalized afterward and checked
  with the full offline suite. Live cycle detections/recoveries above come from
  the saved run, not replayed or retroactively recalculated results.
- README documents feedback, cycle criteria/limitations, recovery budgets,
  baseline selection, and artifacts. CLI help, all source syntax, local links,
  and git diff --check passed. No model/service upgrade or old-result overwrite
  was performed. Changes remain local, uncommitted, and unpublished.
- Remaining problems: model-selected navigation still fails this TV task within
  40 decisions; successful local loop exits can lead to new loops. Detector
  covers selected pose/object state and short exact action cycles, not every
  form of unproductive behavior. More repeated trials and task/scene coverage
  are needed before claiming general improvement.

## November 8, 2026 — Visual playback of simulator actions

- Created a standalone interactive `sequence.html` in the latest feedback run's
  ignored artifact directory: `results/tv_goal_20261108T142204_537547Z/`.
- Includes the original starting screenshot plus all 40 post-decision screenshots,
  with action labels, camera tilt, cycle-warning markers, previous/next buttons,
  a slider, thumbnails, keyboard controls, and optional one-second playback.
  Original PNG bytes are embedded unchanged so the HTML is portable and requires
  no server or external assets. No model or simulator rerun was performed.
- Verified all 41 screenshot files and labels against the saved action trace.
  Selected decisions 15–20 to illustrate the observed look-up/look-down cycle
  and the model-selected forward move after the warning. This gallery reports
  the existing failed TV trial; it does not imply goal success.
- Gallery remains local and ignored with the generated results. Updated this log;
  no commit or publication was performed.

## November 8, 2026 — TV feasibility and remote-control rules verified

- User questioned whether turning on the TV is actually feasible and whether
  the room contains a remote. This should have been verified before interpreting
  the model navigation trials; added a separate scripted check now.
- Initial attempt to inspect files was not executed: automatic approval review
  failed due to a usage limit, not an unsafe-action determination. After the
  user asked to continue, the normal approved retry succeeded; no approval check
  was bypassed.
- Added `scripts/check_tv_feasibility.py` and ran it in a fresh FloorPlan201,
  without model inference. The exact TV from the model trials is toggleable,
  initially off, and not broken: `Television|-02.36|+01.21|+06.24`.
- Found exactly one RemoteControl, pickupable, on SideTable:
  `RemoteControl|-02.58|+00.74|-00.15`, supported by
  `SideTable|-02.11|+00.00|-00.14`. It was not visible from the default camera;
  its reported initial distance was about 2.18 m. No remote was picked up.
- The diagnostic used a recorded scripted teleport to a reachable near-TV
  position, facing the TV. With empty inventory before and after, a normal
  ToggleObjectOn command (explicit forceAction=False) succeeded on its first
  tested pose/command. Metadata changed isToggled false→true, no error,
  isBroken=false, visible=true, distance about 0.812 m. Before/after screenshots
  were saved, and the on-screen image was visually inspected.
- Therefore the direct AI2-THOR goal is feasible without a remote. This is a
  scripted feasibility demonstration only; it does not turn the failed VLM
  episodes into successes or demonstrate autonomous navigation.
- Found an important rule-layer distinction in the pinned external benchmark:
  `../AsgardBench/AsgardBench/scenario.py` around lines 3632 and 3705 rejects TV
  toggling unless a RemoteControl is held. Its high-level do_toggle_on around
  line 4387 also invokes remote pickup as a helper substep. Our custom executor
  uses AsgardBench's parser but calls AI2-THOR directly; it does not apply those
  wrapper rules or helper substeps. Benchmark-faithful remote use and direct
  simulator feasibility must not be conflated.
- Official reference checked for toggle semantics and TV properties:
  https://ai2thor.allenai.org/ithor/documentation/object-state-changes/ and
  https://ai2thor.allenai.org/ithor/documentation/objects/object-types/ .
- Artifacts (local, ignored): `results/tv_feasibility_20261108T170402_201387Z/`
  with result.json (TV/remote/support/inventory metadata, exact setup and command),
  initial_room.png, before.png, and after.png. Old model runs remain unchanged.
- Validation: live command success plus actual power-state/empty-inventory
  assertions, source syntax, documentation links, and git diff --check. No
  additional model trials, training, publication, or remote-policy changes were
  made. Changes remain local, uncommitted, and unpublished.

## November 8, 2026 — Five near-TV Qwen device-selection trials: 5/5 successful

- User authorized the proposed first diagnostic: put the agent near a reachable
  TV, provide only the goal with normal image/control protocol, and repeat five
  times to separate reachable-device selection from navigation.
- Added `scripts/test_tv_selection.py`. Each trial creates a fresh FloorPlan201
  controller and applies the pose verified by the separate feasibility check:
  position (-2.25, 0.9026566744, 5.5), yaw 351.967862°, horizon 32.288996°.
  This is scripted camera setup, not model-selected navigation. It performs no
  TV power interaction during setup; metadata must confirm a visible, working,
  initially-off TV and empty inventory before the first model request.
- Model: qwen3-vl:8b-instruct Q4_K_M, digest
  70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb,
  isolated Ollama 0.40.15 on 11435. Every trial uses empty model history, the
  current screenshot, literal goal “Turn on the TV.”, normal constrained JSON
  and eligible controls, and current goal-status feedback. No route, proposed
  action sequence, example answer, coordinates, or forced model choice is sent.
  All normal eligible object controls and navigation remain available.
- Predeclared cap: five model decisions per trial, with existing failure and
  repetition bounds. **All five trials succeeded on the first decision**:
  TOGGLE_ON Television → unchanged AsgardBench parser → ToggleObjectOn on the
  exact TV instance. All simulator responses succeeded and actual power state
  changed from false to true. No retry, navigation, failure, or recovery was needed.
- Results: 5 valid setups, 5 completed trials, 5 successful trials, 5 first-decision
  successes; five total model requests. This establishes repeated reachable-TV
  action selection in this single configured view, not general reliability,
  navigation competence, distractor robustness, or remote-based benchmark success.
- Direct AI2-THOR semantics were used; no remote was held and AsgardBench's
  extra remote rule was not imposed. The earlier failed distant-start runs
  remain unchanged and must not be relabeled as successes.
- Artifacts (local, ignored): `results/tv_selection_20261108T170809_290349Z/`,
  containing summary.json (all trials, setup pose, server version, model digest),
  and trial_01 through trial_05 with before/after images and complete decision
  prompt/request/raw-response/parser/command/state traces.
- Validation: independently replayed assertions over saved results to confirm
  initial off/visible state, empty inventory, exact first action, simulator success,
  final on state, screenshot files, and goal/control prompt. Script syntax,
  documentation links, and git diff --check passed. No model/service change,
  training, commit, or publication was performed.

## November 8, 2026 — Slightly farther TV start: 5/5 successful at 1.42 m

- User requested placing the agent a bit farther from the TV after five near-TV
  successes. Selected an approximately 0.5 m increase and retained five fresh
  trials, the unchanged goal/control/feedback protocol, and five-decision cap.
- Added `--backoff` (0–3 m) to `scripts/test_tv_selection.py`, recording nominal
  and actual setup commands, measured initial TV state/distance, legal choices,
  and `initial_tv_interactable`. Zero retains the original verified near pose.
- Initial attempt moved directly backward along the previous heading. That
  nominal location collided with CoffeeTable|-02.33|+00.00|+04.92. All five setup
  attempts in that batch failed before any model request. These are setup errors,
  not five failed model trials. Artifacts preserved at
  `results/tv_selection_20261108T171654_323023Z/` (0 valid setups, 0 model decisions).
- Fixed setup selection for positive offsets: query GetReachablePositions,
  select the free position nearest the nominal backoff among those whose TV
  distance is within 0.15 m of the desired baseline distance plus backoff, and
  face the camera toward the TV. No forceAction, scripted navigation, or TV
  interaction is used. Pose/coordinates are not sent to the VLM.
- Valid pose chosen for all five fresh scenes: (-1.75, 0.9026566744, 5.0),
  yaw 334.018721°, existing horizon 32.288996°. Reported TV distance increased
  from 0.811927 m to **1.418375 m** (about 0.61 m farther). The tolerance and free
  grid selection explain the difference from the nominal 0.5 m increase.
  Lateral position and yaw changed to avoid the table, so this is not a strictly
  distance-only image comparison.
- **5/5 valid trials succeeded on the first model decision.** Each selected
  TOGGLE_ON Television; unchanged parser accepted it, ToggleObjectOn succeeded,
  and exact TV power metadata changed off→on. No retries/recovery or navigation
  were needed. Qwen3-VL 8B Instruct/Ollama 0.40.15 settings remain unchanged.
- Important limit: TV power control was already eligible in every starting view
  (within the configured interaction conditions). This demonstrates selection
  from a slightly farther view, not approach/navigation competence. Starting
  beyond the interaction boundary remains a separate test.
- Artifacts (local, ignored): `results/tv_selection_20261108T171755_771806Z/` with
  summary.json and five full trial directories containing images, prompts,
  responses, parsed choices, commands, state, and initial eligibility evidence.
- Validation: independently checked all saved initial distances/eligibility and
  off states, first-action choices, simulator success and final power states,
  screenshot presence, absence of inference in failed setups, source syntax,
  documentation links, and git diff --check. README documents the offset,
  reachable-pose policy, tolerance, and interpretation limits. No model/service
  changes, training, commit, or publication were performed.

## November 8, 2026 — Exactly one forward step then TV power-on: 5/5 successful

- User requested a starting position where the model must walk one step before
  turning on the TV. Rather than infer eligibility from center distance, verified
  the exact simulator interaction boundary with a separate scripted calibration.
- Added `scripts/calibrate_tv_step.py`: queries reachable positions and tests
  candidate poses with ordinary, unforced actions. The selected pose rejects
  ToggleObjectOn at the start; one MoveAhead of 0.25 m succeeds and makes the TV
  eligible; ToggleObjectOn then succeeds. This calibration is setup evidence,
  not a VLM trial, and its actions are never used as model demonstrations.
- Verified fixture: FloorPlan201, position (-3.0, 0.9026566744, 4.5), yaw
  20.221965°, horizon 32.288996°. Initial reported TV distance 1.884769 m,
  visible=false/isToggled=false; after one forward step, distance 1.638518 m,
  visible=true. The initial rejected toggle reported target not found within
  visibility; final unforced toggle succeeded. This demonstrates again that
  reported object-center distance is not identical to interaction eligibility.
- Calibration artifacts: `results/tv_one_step_calibration_20261108T172059_734224Z/`
  contains candidate evidence, verified fixture, and before/middle/after images.
- Added `--one-step-fixture` to `scripts/test_tv_selection.py`, mutually exclusive
  with nonzero backoff. It loads the verified pose, records file hash/provenance,
  and asserts each fresh trial starts with an off, working, initially ineligible
  TV and empty inventory. Only a camera teleport occurs during model-trial setup;
  no scripted walking or toggling occurs there.
- Ran five fresh Qwen3-VL 8B Instruct trials on isolated Ollama 0.40.15, with the
  unchanged goal “Turn on the TV.”, normal screenshot/control/feedback protocol,
  full eligible controls, empty history, and five-decision cap. The model was
  not told the pose, calibration, number of required steps, or action sequence.
- **All 5/5 trials succeeded in exactly two decisions**, independently selected:
  1. MOVE_AHEAD None → MoveAhead 0.25 m; goal still incomplete, TV now eligible.
  2. TOGGLE_ON Television → unchanged object parser → ToggleObjectOn on the
     exact TV instance; simulator success and power state false→true.
  No retries, repetition warnings, extra looks/rotations, or command failures.
  Ten total model requests; zero first-decision goal completions (as required).
- Artifacts: `results/tv_selection_20261108T172152_007323Z/` contains summary.json,
  fixture hash, all five complete trial traces, and before/middle/after images.
  Middle images are unchanged copies of each first decision's saved after image;
  the convenience copy and clearer fixture label were added after the run.
- Validation: independently checked all five actual camera displacements equal
  0.25 m (within 0.0001 m), initial exclusion/next-request inclusion of Television
  under TOGGLE_ON, exact two-action order, all simulator success flags, power
  states, prompts with no one-step hint, screenshot files, source syntax, local
  documentation links, and git diff --check. No core agent algorithm changed.
- This establishes a repeated short approach-plus-interaction result from one
  calibrated view under direct AI2-THOR rules, not general navigation, remote-
  based benchmark success, or recovery from arbitrary room starts. Earlier failed
  long-distance experiments remain unchanged. README documents reproduction.
  Changes remain local, uncommitted, and unpublished.

## November 8, 2026 — Verified three-step TV start: model 0/5 within five decisions

- User requested moving the start to three forward steps away from interaction
  range. Generalized `scripts/calibrate_tv_step.py` with --steps (1–10), and
  `scripts/test_tv_selection.py` with --step-fixture, calibrated step counts,
  and exact N-walks-then-toggle trajectory counts. Retained --one-step-fixture
  as an alias and compatibility with the earlier one-step fixture format.
- Calibration found a reachable pose: (-3.5, 0.9026566744, 4.25), yaw
  29.802860°, horizon 32.288996°. TV center distance was about 2.319620 m.
  Rejected normal ToggleObjectOn attempts at zero/one/two forward moves, and
  succeeded after the third. Distances at the four checks were approximately
  2.319620, 2.072022, 1.825080, and 1.579099 m. Visibility flags false/false/false/
  true show the actual eligibility boundary; all three 0.25 m moves succeeded.
- Calibration tried three candidate poses. Independently repeated the selected
  setup and commands in a pristine scene after the model trials, confirming
  power-on outcomes [false, false, false, true]. This excludes candidate-search
  state as the explanation for the verified approach. Both checks used normal
  physics and explicit forceAction=False for object actions, without a remote.
- Calibration artifacts: `results/tv_step_calibration_20261108T175358_437256Z/`,
  including result.json, fresh_verification.json, before/after images, and images
  after each scripted calibration move. Calibration is not a VLM success claim.
- Ran five fresh Qwen3-VL 8B Instruct trials on isolated Ollama 0.40.15 with the
  same “Turn on the TV.” goal, screenshot/control/feedback protocol, full normal
  eligible controls, empty history, and five-decision cap. Fixture coordinates,
  required step count, route, and example sequence were not sent to the model.
  Only camera teleportation was used for each trial's initial setup.
- **0/5 model trials achieved the goal within five decisions.** Every trial
  independently chose the same valid sequence: MOVE_AHEAD, ROTATE_RIGHT,
  ROTATE_RIGHT, MOVE_AHEAD, ROTATE_LEFT. All commands executed successfully;
  no parser/schema/physical-command failure occurred. The model turned away
  instead of taking the three verified straight steps, and never attempted
  TV power-on. Goal remained incomplete and TV off at decision_limit.
- Five decisions were enough for the ideal four-action approach plus one spare
  action. The failed outcomes do not establish failure with an unlimited or
  larger budget. Model navigation still fails from this particular three-step
  pose despite the prior 5/5 one-step successes; different views/poses and the
  modest sample size prevent broader reliability conclusions.
- Model artifacts: `results/tv_selection_20261108T175446_300090Z/` with summary.json,
  calibrated fixture/hash, five before/after screenshot pairs, and all 25
  decision request/response/parser/command/feedback/state traces. Setup validity
  was 5/5; exact three-walk-then-toggle success count was zero.
- Validation: independent saved-result checks confirmed setup identity, initial
  TV unavailability/off state, identical five-action trajectories, all execution
  success flags, final off state, unhinted goal prompts, and screenshot presence.
  Fresh-scene calibration proof, script syntax, CLI help/compatibility options,
  local documentation links, and git diff --check passed. README now documents
  general N-step calibration and the five-decision test interpretation. No core
  model prompt/policy/service changes, training, commit, or publication occurred.

## November 8, 2026 — Screenshots of the failed three-step model trial

- Presented the original initial image and five successive post-action images
  from trial_01 of `results/tv_selection_20261108T175446_300090Z/`.
- Checked screenshot paths and labels against the saved model trace: forward,
  right, right, forward, left. These show the actual model-selected trajectory,
  not the successful scripted three-forward-step calibration.
- No images were edited and no model/simulator rerun was performed. TV stayed
  off in this trial. Updated the progress log; no publication was performed.

## November 8, 2026 — Diagnosis of the three-step navigation failure

- Inspected trial_01's original start, first-forward, and first-right-turn images
  alongside its actual prompt/control lists. The TV is clearly rendered in the
  first two views. Turning right shifts it toward the left edge; subsequent
  model actions depart from the scripted feasible straight approach.
- Observed interface limitation: before reaching interaction range the eligible
  control list names only PICKUP Bowl and navigation, omitting Television and
  TV power commands entirely, despite the TV being rendered in the image.
  This conflates in-image perception with simulator interaction eligibility.
  Near-TV tests were easier partly because TOGGLE_ON Television was already an
  eligible named choice; their success alone does not prove visual navigation.
- Observed feedback limitation: the model receives successful movement and
  “goal remains incomplete,” but no explicit distinction between TV rendered
  versus currently unreachable. It gets no target location/route (by design).
- Hypothesis, not established cause: the pipeline fails to maintain a visual
  target/approach plan across several decisions, amplified by the changing
  object/action vocabulary. The trace does not establish whether the model
  misrecognizes objects, misjudges obstacles, or chooses a poor plan internally.
- Proposed next comparison: separate rendered/known target observations from
  currently eligible actions and provide factual TV reachability/status feedback,
  without a route or required step count. Keep Qwen and the calibrated start
  unchanged. This would be a new assisted-feedback protocol, not an unchanged
  vision-only baseline. No code/prompt changes or new inference were performed
  during this diagnosis. Updated this log only; no publication.

## November 8, 2026 — Assisted rendered-object feedback experiment: 0/5

- User approved testing the proposed separation between objects rendered in the
  screenshot and objects eligible for interaction. Added reusable
  `household_agents/observations.py`, optional scene feedback in the goal episode,
  and `--scene-observations` in `scripts/test_tv_selection.py`. Existing runs keep
  the original protocol unless explicitly enabled.
- Enabled AI2-THOR instance segmentation only for this option. Camera labels use
  `instance_detections2D` pixel evidence rather than the range-limited `visible`
  flag. Rendered objects receive type, interaction status, currently eligible
  actions, and capability-relevant power/open/pickup states. Off-screen metadata
  is excluded. This is simulator-assisted perception, not a vision-only test.
  Official API references checked:
  https://ai2thor.allenai.org/ithor/documentation/environment-state/ and
  https://ai2thor.allenai.org/ithor/documentation/initialization/.
- Model-visible observations contain no instance IDs, bounding boxes, world/image
  coordinates, distances, route, or required move count. Raw rendering evidence
  is saved separately in each decision's scene_observations.json. The action
  schema, parser, executor, and physical eligibility rules were not relaxed.
- Ran five fresh Qwen3-VL 8B Instruct trials on isolated Ollama 0.40.15, with the
  same verified three-step fixture, camera pose, goal, model digest, normal
  controls, empty inventory, and five-decision cap as the earlier comparison.
  Initial feedback correctly named Television, in_view=true, isToggled=false,
  not_currently_interactable, eligible_actions=[]. Rendering evidence placed the
  TV at bbox [259, 103, 371, 197] while its simulator visible flag was false.
- **0/5 achieved the goal.** All five independently selected ROTATE_RIGHT five
  times, turning 225 degrees without translation. All 25 outputs parsed and all
  25 simulator actions succeeded; every trial stopped at decision_limit with
  the TV still off. No TV power command was attempted. Setup validity was 5/5.
- Compared with the earlier 0/5 sequence (forward, right, right, forward, left),
  this protocol changed behavior but did not improve success. Verified that
  initial setup commands and legal controls match the earlier saved trials.
  Providing the TV label and range/state distinction alone was insufficient in
  this configuration. The cause of the model's choice remains unestablished;
  spatial target tracking and action selection remain hypotheses. This option
  supplies no target direction. Repeated rotations change camera pose, so five
  turns do not satisfy the existing repeated-state cycle detector; no recovery
  was triggered. A longer budget could produce a different outcome.
- Comparison limits: five repeats share one scene/pose and temperature zero;
  they do not establish general reliability. The prompt and instance-rendering
  setting changed, and metadata provides ground-truth labels/states. This is an
  assisted protocol comparison, not an isolated test of model perception.
  Initial RGB images were identical in one matched trial pair; four pairs had
  small pixel differences despite matching camera poses (mean absolute channel
  difference 0.131–0.187 on the 0–255 scale). Inputs were not byte-identical.
- Artifacts: `results/tv_selection_20261108T184147_550638Z/` contains summary.json,
  five trial results, before/after and per-decision screenshots, exact prompts,
  request/response/parser/command traces, observation evidence, and snapshots of
  the three executed source files under protocol_sources/. The verified fixture
  remains `results/tv_step_calibration_20261108T175358_437256Z/result.json`.
- Code review after the live run found a generalization bug in the new helper:
  a type-level legal choice could incorrectly give another rendered instance of
  that type the same eligible action. Reused executor instance candidates to
  enforce each instance's visibility, state, inventory, and task binding. Added
  a regression test covering near/off, far/off, and near/on instances. The live
  scene's single TV observation was unaffected; exact executed code was preserved
  before this correction, and the live run was not silently replaced or rerun.
- Validation: 40 offline tests passed before inference; the additional instance
  regression brings the final suite to 41 tests, all passing. Verified saved trial outcomes,
  setup/control matching, initial rendered TV feedback, simulator success flags,
  final power state, and screenshot presence; verification.json records these
  checks. Source syntax, CLI help, local documentation links, and git diff
  --check passed. README documents the option and
  assisted-perception scope. No model/service changes, commit, or publication.

## November 8, 2026 — Existing-image TV direction diagnostic

- User requested testing the existing images to see which direction Qwen would
  recommend. Added reusable `scripts/diagnose_direction.py` with configurable
  target, images, model, and endpoint. Each screenshot receives a fresh request;
  there is no simulator startup, parser call, action execution, or history.
- Tested 12 original images: initial plus five post-action frames from trial_01
  of both `tv_selection_20261108T175446_300090Z` and
  `tv_selection_20261108T184147_550638Z`. Used the same installed Qwen3-VL 8B
  Instruct digest and isolated Ollama 0.40.15, temperature zero, no retries.
  The prompt asks for horizontal target position and one approach movement;
  no simulator labels, coordinates, route, or reference answer were supplied.
- **11/12 position classifications agreed with visual review.** All three
  centred-TV images produced CENTER + MOVE_AHEAD. All three left-edge TV images
  produced LEFT + MOVE_BACK. Of six absent-TV images, five produced NOT_VISIBLE
  and one falsely reported LEFT in a wall view; all six proposed NONE as
  requested for unsupported movement. All 12 outputs completed and validated.
- The forward proposals agree with the earlier verified straight approach.
  Left-edge views still produced backward movement rather than camera alignment
  toward the target. These proposals were not executed: avoidance manoeuvres
  and physical success/failure were not established. This is a direction
  diagnostic, not a newly successful TV episode or an implemented planning fix.
- Evidence narrows the earlier hypothesis: the model can often locate the TV
  when explicitly asked. The exact assisted initial screenshot now produces
  forward instead of the original episode's right turn. However, task wording,
  history, controls, output fields, and NONE option also differ; this does not
  isolate one causal prompt component. The 12 related images cover one scene
  with no right-side-TV example, so 11/12 is not a general accuracy estimate.
- Detailed answers, comparison, and limitations:
  [TV direction diagnostic report](reports/tv_direction_diagnostic_2026-11-08.md).
  Raw artifacts and screenshot comparison gallery:
  `results/direction_diagnostic_20261108T194208_867086Z/` (report.html,
  evaluation.json, summary.json, prompt, executed source snapshot, per-image
  original PNG/request/response/result files). Inputs were copied byte-for-byte;
  no image transformations were used. Reference labels were added separately.
- Validation: source/request/copied-image SHA-256 agreement, all saved raw versus
  parsed answers, identical prompts/options across requests, expected model
  digest, script syntax, CLI help, local documentation links, and git diff
  --check passed. README documents reuse. The action pipeline was unchanged;
  no additional simulator experiment, model/service change, commit, or push.

## November 8, 2026 — Explicit perception before live action: 0/5

- User approved implementing the explained locate → choose → execute → inspect
  loop. Added reusable `household_agents/perception.py`: an image-only locator
  with a strict target_position schema and memory of previous/last-seen visual
  locations. Refactored the Ollama image transport into a shared method while
  retaining the existing action schema and AsgardBench parser behavior.
- The optional episode mode asks for location before every action. Action
  feedback supplies that VLM estimate, goal interaction availability, and an
  approach/locate/recover/interact phase. A lost or uncertain previously seen
  target receives recovery guidance. No route, world/image coordinates, fixed
  step count, or automatic direction-to-action mapping is supplied; the model
  still chooses every action through the same validated execution path.
- Added `--locate-before-action` to both TV entry points. The trial runner
  separates this mode from simulator-assisted scene observations. Baseline
  history-only mode cannot enable it. No ground-truth rendering labels are
  given to the locator; legal controls retain normal simulator eligibility.
- Invalid perception prevents the action request and all execution, counts
  toward existing bounded failure/decision limits, and supplies its validation
  error to the next perception attempt. Runtime failures terminate immediately.
  Each decision preserves perception and action requests/responses independently
  with the same source image, tracking feedback, and before/after screenshots.
- Validation before inference: all **47 tests passed** (41 existing + six new).
  New coverage includes interleaved fresh-image perception/action requests,
  three forward moves before power eligibility, lost-target memory and recovery,
  invalid-perception rejection/retry/exhaustion, strict location validation, and
  terminal transport errors. Fake-controller success is not model evidence.
- Ran five fresh Qwen3-VL 8B Instruct trials on isolated Ollama 0.40.15 from
  the same verified three-step fixture with five action decisions per trial.
  This adds up to five perception requests, rather than increasing the action
  budget. Artifacts: `results/tv_selection_20261108T200722_257761Z/`, including
  exact executed source snapshots in protocol_sources/.
- **0/5 reached the goal.** Each trial produced the same five perception/action
  pairs: CENTER/right, LEFT/right, NOT_VISIBLE/right, NOT_VISIBLE/right,
  LEFT/right. Every trial stopped at decision_limit with the TV off and without
  attempting power-on. Setup validity was 5/5; all 25 simulator turns succeeded.
  All 25 perception and 25 action outputs completed normally and validated.
- The third and fourth requests correctly entered recover phase and retained
  the LEFT estimate from decision 2 as the last seen location. Actual action
  prompts explicitly asked to bring the lost target back into view, but the
  model continued turning right. At decision 5 it falsely reported LEFT in a
  wall view, switching the tracker back to approach. This illustrates both a
  visual false positive and action choices that remain ineffective despite
  receiving a correct centre/left estimate earlier in the trial.
- This mode did not improve on the earlier 0/5 three-step protocols. It shows
  that making the location estimate explicit is insufficient under this model,
  action prompt, and five-decision budget. It does not establish the internal
  cause of the repeated right-turn choices. Interaction-phase success remains
  covered by fake-controller tests only for this new mode; live trials never
  reached that phase. No automatic action correction or successful physical
  recovery is claimed. No prompt/budget changes or reruns were used to replace
  these failed results.
- Independent artifact checks confirmed identical model digest, fixture hash,
  setup commands, initial legal choices, and action budget versus the earlier
  three-step baseline. Each perception/action pair used byte-identical fresh
  input images and identical inference options. Verified that location appears
  in the action prompt, location requests contain no simulator labels, recovery
  feedback is present, all outputs/commands succeeded, and final TV power is off.
  See verification.json for checks and sequence.html for the representative
  before/after process, including the false-positive wall view.
- Comparison limits: five deterministic repeats share one scene/pose; action
  prompting and target memory changed, and inference increased from one to two
  calls per action decision (50 total requests here). The modest action budget
  remains a limit. Results do not establish failure with a longer budget or
  general perception/navigation accuracy. README documents the opt-in command,
  failure policy, trace layout, and inference cost. Source syntax, both CLI help
  checks, invalid-option handling, local documentation links, and git diff
  --check passed. No model/service changes, commit, or publication.

## November 8, 2026 — Traced right-turn origin across the parser boundary

- User asked whether the reported right turn originated in Qwen or was changed
  by AsgardBench. Inspected the saved raw model-server response, validated
  action, local navigation adapter, simulator command, and observed camera yaw
  for all 25 executed decisions in
  `results/tv_selection_20261108T200722_257761Z/`.
- Every raw response already contains action=ROTATE_RIGHT, object=None. Each
  validated trace labels parser=local_navigation, and each simulator command is
  RotateRight with degrees=45. Navigation in this custom demo bypasses the
  AsgardBench action parser and calls AI2-THOR through our explicit adapter;
  supported object interactions retain the separate AsgardBench parser path.
- All 25 actual camera yaw changes were +45 degrees within 0.001 degrees,
  modulo 360. For trial_01/decision_01, yaw changed from 29.802858° to
  74.802864°, with unchanged position and simulator success. No direction
  reversal or substitution occurred between the raw output and execution.
- Evidence locates this choice upstream of command conversion. It does not
  establish why Qwen/Ollama produced the right-turn response. No new inference,
  simulator run, implementation change, commit, or publication was performed;
  only artifact/code inspection and this log update.

## November 8, 2026 — Controlled action prompt/schema comparison

- User approved the proposed four-condition comparison using the existing
  centred and left-side TV images. Added `scripts/compare_action_requests.py`
  and tested current versus short prompts, each with schema enforcement on/off,
  on trial_01/decision_01 and decision_02 from
  `results/tv_selection_20261108T200722_257761Z/`.
- Eight independent requests used the same Qwen digest, Ollama 0.40.15, image,
  goal, eligible controls, location estimate, factual feedback/history, and
  inference options within each view. The current/schema request exactly
  reproduced its source. Schema pairs differed only by removing API `format`;
  no format=json fallback was used. The short prompt retained the exact factual
  feedback while reducing/reformatting instructions. The second image reversed
  condition order. No simulator, action execution, retry, or repair was used.
- **Removing schema changed none of the four paired answers.** The centred-TV
  image produced ROTATE_RIGHT in all four conditions. The left-side image
  produced ROTATE_RIGHT with the current prompt and MOVE_AHEAD with the short
  prompt, independently of schema enforcement. All eight outputs finished
  normally and passed strict action/object validation; no malformed answers or
  transport errors occurred.
- Evidence does not support schema enforcement alone causing these right turns
  on these inputs. Prompt changes affected the left-side proposal but did not
  resolve the initial centred-TV choice. Forward on the left-side image was not
  physically executed/validated and is not a task-success claim. Broader cause
  remains open: only two related views and one request per condition were tested,
  with no independent claim about prompt length versus individual wording.
- Detailed controls, full result table, limitations, and reproduction command:
  [Action prompt/schema comparison](reports/action_prompt_schema_comparison_2026-11-08.md).
  Raw artifacts: `results/action_request_comparison_20261108T204657_782271Z/`
  with screenshot/report.html, verification.json, original source/feedback,
  exact prompts, raw responses, validation results, and executed source snapshot.
- Validation confirmed input/source/copied-image SHA-256 agreement, exact source
  request reproduction, format-only differences within each pair, identical
  options, original model/server identity, factual-feedback preservation, all
  raw versus parsed answers, script syntax, CLI help, documentation links, and
  git diff --check. README documents reuse. The live action pipeline was not
  changed; no model/service changes, commit, or publication.

## November 8, 2026 — Broader diagnosis and minimal action prompt: TV success

- User authorized broader diagnostic work. Added reusable
  `scripts/diagnose_action_pipeline.py` for controlled saved-request probes:
  tracking/history removal, tracking instructions versus data, navigation-only
  controls, minimal turn-on versus approach goals, omitted images, intentionally
  conflicting location estimates, text-only direction/copy checks, direction
  output contracts, generation settings, and beginning/end baseline replays.
  No simulator action is executed by the probe runner.
- First batch: `results/action_pipeline_diagnosis_20261108T205700_491107Z/`,
  33 completed valid outputs. The centred image changed right→forward after
  removing target tracking; minimal prompts produced forward under both goals.
  Copy and text-only ahead/left/right checks all matched expected actions.
  Baseline end replays still returned right. Sampling variants did not produce
  forward in the six centred-baseline probes. The left view showed additional
  prompt/history sensitivity. These saved-image observations motivated the
  follow-up isolation and separately recorded live trials below.
- Read runtime version/tags/active models, Qwen template/parameters, and isolated
  logs. The observed native requests had no truncation; actual repeat_penalty was
  1.0. Official reference checked for chat format and model unloading:
  https://docs.ollama.com/api/chat. Qwen's published Instruct evaluation settings
  were checked at https://github.com/QwenLM/Qwen3-VL#evaluation-reproduction;
  the sampled probe profile changes multiple parameters and is labeled as such.
- Both installed servers were idle before testing. Shared Ollama 0.6.2 has
  LLaVA 7B; isolated Ollama 0.40.15 has Qwen3-VL 8B Instruct. No downloads,
  runtime installation changes, or source pipeline modifications were made during
  these saved-request probes.
  Model default/template display alone is not evidence of a template defect.
- Completed **68 valid saved-request probes**: 33 broad Qwen cases; 24 tracking
  field ablations in `results/action_pipeline_diagnosis_20261108T205844_952783Z/`;
  two original-request replays following model unload in
  `results/action_pipeline_diagnosis_20261108T205952_485360Z/`; and nine installed
  LLaVA cases in `results/action_pipeline_diagnosis_20261108T210039_763623Z/`.
  No transport/validation errors or repairs occurred. The cold centred replay
  and subsequent left replay retained right turns, arguing against dependence
  on the earlier loaded context. LLaVA chose forward on the centred rich prompt
  but right on the left rich prompt; its minimal prompts chose forward. This
  compares model/runtime stacks, since LLaVA uses Ollama 0.6.2, not weights alone.
- Tracking-field sweep: removing current or goal_interaction changed the centred
  answer to forward; other individual removals retained right. All corresponding
  left-view field cases still chose right. A minimal action context worked on
  both images under both final and approach goals. There is no single universal
  bad field identified. Image omission also changed right→forward; conflicting
  location tests and basic text/copy checks showed that both images and textual
  context affect generation. Internal model reasoning remains unknown.
- Temporarily unloaded models between comparisons to avoid simultaneous GPU
  residency. An immediate empty-runtime assertion after the old shared server's
  unload acknowledgment failed; a later check confirmed the unload completed.
  This was asynchronous cleanup reporting, not a model-inference failure.
  Shared runtime configuration/models were unchanged and it returned to idle.
- Implemented the diagnostic-derived reusable minimal_goal_prompt and explicit
  `--action-prompt minimal` option in both TV entry points. Standard remains the
  default for historical comparisons. The minimal variant uses the image, goal,
  eligible controls, movement semantics, and a brief VLM location estimate. It
  omits ordinary full tracking JSON/successful history, but still supplies lost
  target, latest error, and repetition feedback when applicable. Strict schemas,
  bounded validation, simulator execution/feedback, and state verification remain.
  No fixed route or direction-to-action rule was added.
- **Live controlled result: 5/5 succeeded** from the same verified three-step
  start, with the same Qwen model, five-decision budget, normal controls, and
  simulator rules as the rich-prompt 0/5 batch. Every fresh trial chose exactly
  MOVE_AHEAD ×3 followed by TOGGLE_ON Television. All 20 commands succeeded and
  actual TV power changed off→on. Power control was eligible only at decision 4.
  Artifacts: `results/tv_selection_20261108T210200_939530Z/`, including source
  snapshots, verification.json, before/middle/after and full sequence.html.
- **Harder original-start check: 1/1 succeeded in 16 decisions**, against a
  40-decision cap. No setup positioning or teleportation occurred. Qwen chose
  15 normal forward moves followed by TV power-on. Initial reported centre
  distance was 5.031 m and final 1.945 m; actual interaction eligibility and
  changed power state verify success. Artifacts:
  `results/tv_goal_20261108T210329_321491Z/`, with verification, source snapshots,
  middle.png and the complete 17-frame sequence.html. This uses the direct
  simulator demo, not AsgardBench's holding-a-remote scenario rule.
- Strongest evidence points to a prompt/context interaction in the action model,
  rather than a reversed parser mapping, schema enforcement alone, or inability
  to understand basic directions. The minimal variant fixes these tested starts;
  no universal root cause or general navigation reliability is established.
  Five controlled trials share one pose; the default start was checked once.
  One matched initial image was identical to the rich batch; four had small
  rendering differences (mean channel difference 0.123–0.187/255). Saved-image
  ablations held bytes fixed. Broader scenes, collisions and recovery remain open.
- Full controls, tables, interpretation, remaining limitations, artifact paths:
  [Action-pipeline diagnosis report](reports/action_pipeline_diagnosis_2026-11-08.md).
  All 47 regression tests passed after integration. Verified probe construction,
  exact source/input hashes and raw/parsed responses, model/server metadata,
  same fixture/options/initial controls, paired perception/action screenshots,
  all live action sequences, interaction eligibility timing, and power changes.
  Source syntax, CLI help, invalid-option handling, local doc links, and git diff
  --check passed. README documents the new options. No new model download,
  permanent sampling change, runtime update, commit, or publication.

## November 12, 2026 — Preserve navigation and diagnostic work in Git

- User requested a local Git checkpoint of the pending project work. Reviewed
  the tracked diff and pending source, scripts, tests, reports, and documentation.
- Preserved goal-only navigation and power controls, ordered procedures,
  state-aware repetition handling, optional rendered-object observations,
  VLM target perception, minimal action prompting, isolated Qwen launcher,
  calibration/selection runners, and saved-request diagnostic tools and reports.
- Validation: all 47 existing offline regression tests passed on this date;
  reviewed credential-pattern matches (only documented local Ollama placeholders
  and descriptive text), and confirmed generated results remain ignored.
- This checkpoint preserves the previously recorded live evidence; no new
  inference, simulator experiment, benchmark run, or GitHub publication was
  performed. Broader navigation reliability and benchmark integration remain open.

## November 12, 2026 — Varied-position and task evaluation

- User requested live evaluation across different positions and tasks. Added
  `scripts/evaluate_goals.py` using the existing Qwen3-VL 8B Instruct, minimal
  action prompt, image-only target locator, normal controls, validation, feedback,
  and goal-state verification. No model or action-policy change.
- Planned 15 fresh-scene trials: TV power-on in FloorPlan201 and FloorPlan202,
  fridge OPEN/CLOSE and Mug PICKUP in FloorPlan1, each from a near eligible
  centered view and two farther ineligible angled views. Twenty decisions per
  trial, one trial per condition, no automatic trial reruns.
- Setup uses reachable positions and rendered-instance evidence to select
  an initially rendered target, and normal interactions to establish an unfinished
  goal when needed. This is assisted initial placement/state, not autonomous
  discovery. Setup metadata is not passed as visual labels or a route to the model.
- Initial inspection verified targets and reachable positions in all three rooms;
  local Qwen/Ollama identity matches the previous experiments and both servers
  were idle. Script syntax and CLI help passed. The first batch was launched under
  `results/goal_evaluation_20261112T092905_544359Z/`; raw action/perception requests,
  responses, screenshots, setup attempts, source snapshots, and incremental
  summaries are preserved. No benchmark run or publication.

- Completed the original matrix with **14/15 successes** and no setup errors:
  both TV rooms and fridge OPEN/CLOSE scored 3/3, Mug PICKUP scored 2/3. Thirteen
  episodes had no decision errors. The left-angle FloorPlan202 TV needed 13
  decisions and two repetition rejections before success. The failed left-angle
  Mug trial proposed an invalid PICKUP Cabinet (correctly rejected), picked up
  the wrong Bowl, hit the island three times, and stopped at the repetition limit
  after 14 decisions. Mug remained unpicked; no PUT/DROP recovery is supported.
- Added an explicit `default_start` variant and separately ran four follow-up
  trials from original scene poses/states with no setup actions. **3/4 succeeded**:
  FloorPlan201 TV in 16 decisions (15 forward moves then power-on), fridge OPEN
  in one decision (already interactable), Mug PICKUP in eight decisions after
  two simulator camera-limit rejections. FloorPlan202 TV failed at the unchanged
  20-decision cap after picking up a remote and ineffective movement/look actions;
  TV remained off. No failed episode was rerun or replaced.
- Follow-up artifacts: `results/goal_evaluation_20261112T093427_664213Z/`.
  Both batches include independent verification.json, overview.html, source
  snapshots/hashes, a local verification helper, complete model/action/image
  evidence, and a matching end-of-run runtime identity check. Verified 194 model
  requests, 97 decisions, 91 executed commands, 19 actual final goal states,
  paired perception/action images, inference options, source/image hashes, and
  13 yaw changes. One invalid action/object pair was not executed; five physical
  execution errors and five repetition rejections were preserved.
- Overall descriptive outcome: **17/19 successes**, comprising 15 error-free
  episodes, two successes after recovery, and two failures. This is one episode
  per condition under two different starting protocols, not a general reliability
  estimate. Initial placement was assisted only in the first 15; all subsequent
  actions were model-selected. Most successful angled starts needed only short
  approaches. No navigation policy, prompt, model, or sampling fix was introduced
  to improve a failed result; only the evaluation runner was extended for the
  explicitly separate default-start protocol.
- Validation: all 47 existing offline regression tests passed; script syntax,
  CLI help, local documentation links, and git diff --check passed. Visually
  inspected representative failed Mug/TV and successful Mug screenshots.
  Added reproduction instructions to README and the detailed
  [varied-goal report](reports/goal_generalization_2026-11-12.md).
- Remaining issues now have live evidence: wrong-object pickup/full inventory,
  island collision avoidance, camera-limit awareness, and off-screen target
  search/navigation. The official benchmark remains unchanged. New evaluation
  code, README/log changes, and report are local and have not been committed
  or published in this task.

## Open issues and next work

- Reliability: schema-constrained output and bounded recovery are implemented
  and tested. Repeated near-TV and one-step successes were measured, but reliable
  longer navigation and live physical-failure recovery remain unestablished.
  Invalid responses are still checked rather than assumed impossible.
- Generalization: shared OPEN/CLOSE/PICKUP paths have live examples, but repeated
  runs and broader scenes/objects remain unmeasured. Successful formatting does
  not imply correct or feasible action choice.
- The full benchmark has not been run. The original LLaVA sanity result was
  **0/2**; the November 12 Qwen baseline passed **2/2** after correcting runtime
  context allocation (see the dated report below). The custom agent interface
  has not been integrated into the official benchmark path.
- Object demos use scripted positioning. The goal-only episode now exposes
  model-selected navigation, but the first TV run did not reach its goal and
  reliable navigation or general multi-step planning remains unestablished.
- Context retention and original full-format failure are not fully resolved.
- Shared Ollama remains unchanged. User-authorized isolated Ollama 0.40.15
  and Qwen are installed on 11435. Near-TV and one-step trials succeeded 5/5;
  distant navigation failed, and both three-step protocols scored 0/5 within
  five decisions. The subsequent explicit VLM-location/action protocol also
  scored 0/5 despite correct initial direction estimates and lost-target feedback.
  The subsequent minimal action prompt succeeded 5/5 at that same three-step
  start and once at the default room start. Broader evaluation, physical-failure
  recovery, and other scenes/objects remain open. Explicit goal feedback and short-cycle
  recovery work locally but have not made longer TV navigation reliable.
- GitHub shell authentication remains unavailable; publication uses the connected
  app. The earlier local/remote base mismatch was resolved during publication.

## November 12, 2026 — Clarified official sanity-check scope

- Inspected the two local sanity task definitions and benchmark request/execution
  paths to explain the earlier 0/2 result. Both tasks require television power-on,
  in FloorPlan202 and FloorPlan203, with prescribed poses, randomized object
  setups, and seeds. The scenario requires holding a RemoteControl before
  toggling a visible television; custom direct-simulator demos bypass that rule.
- Confirmed the official actor uses OpenAI-compatible chat requests and the
  benchmark's own prompt/parser path, rather than our native-schema agent loop.
  Proposed a Qwen baseline rerun before separately labeled interface integration.
  No benchmark, model inference, simulator run, or implementation change occurred.


## November 12, 2026 — Official Qwen sanity evaluation (in progress)

- User authorized the unchanged official two-task sanity baseline. Qwen3-VL
  8B Instruct is available on isolated Ollama 0.40.15, port 11435. Benchmark
  checkout is clean at 4d38d380362d767893611fc160dc78665d1356b8.
- First launch failed before any model action: the OpenAI-compatible request
  contained 5,804 tokens but the default runtime context was 4,096. The official
  runner then crashed in TestResult ratio calculation with ZeroDivisionError
  because zero steps had executed. This is a runtime/configuration launch failure,
  not a completed 0/2 agent evaluation. Preserved artifacts:
  results/asgard_sanity_qwen_20261112T095511_346796Z/.
- Created a separate local model alias qwen3-vl:8b-instruct-sanity-ctx16k with
  num_ctx=16384. Verified identical weight blobs, template, capabilities, and
  existing sampling parameters; original model remains unchanged. No downloads
  or changes to the benchmark source, prompt, parser, tasks, rules, or limits.
- Corrected-context run: results/asgard_sanity_qwen_ctx16k_20261112T095624_651245Z/.
  Separate output root preserves earlier results; manifest, source/task snapshot,
  hashes, full model metadata, console log, config, and task traces are saved.
  Runtime /api/ps confirmed 16,384 context. First room passed in four actions;
  the second room was still running when this entry was written.


## November 12, 2026 — Official Qwen sanity baseline completed: 2/2

- The corrected-context run completed with exit 0: FloorPlan202 passed in four
  high-level actions (FIND RemoteControl, PICKUP RemoteControl, FIND TVStand,
  TOGGLE_ON Television); FloorPlan203 passed in three (FIND RemoteControl,
  PICKUP RemoteControl, TOGGLE_ON Television). All seven actions succeeded and
  parsed correctly, with no reported API/action errors or retries. Each TV was
  toggled while holding the remote; the live goal evaluator confirmed power on.
- This is success after fixing the launch configuration, not first-launch
  success. The aborted 4K-context launch and subsequent zero-step reporting bug
  remain preserved separately. The completed tasks were not rerun or replaced.
- Independently reparsed all raw response texts and matched executed actions;
  checked held-remote observations, live goal messages, both official results,
  exit status, source/task snapshot hashes, same alias weight blobs/template/
  existing parameters, and active 16K allocation. All final verification checks
  pass. The first post-run cleanliness check failed due to a generated tracked
  placement cache; preserved the generated cache/diff and initial verification,
  then restored the initially clean checkout's cache. Benchmark checkout is clean.
- Artifact bundle: results/asgard_sanity_qwen_ctx16k_20261112T095624_651245Z/,
  including verification.json and a pre-action screenshot/raw-response overview.
  Detailed findings, failed launch, controls, limitations, and reproduction:
  [Official Qwen sanity report](reports/official_sanity_qwen_2026-11-12.md).
- Important scope: this evaluates the official AsgardBench actor and high-level
  FIND/PICKUP/TOGGLE actions, whose executor handles positioning/subactions.
  It does not establish independent primitive navigation or evaluate our custom
  minimal-prompt/schema agent. One episode per task is not a reliability estimate.
  No benchmark-rule/prompt/source changes, full benchmark, adapter integration,
  commit, or publication. Original model and shared Ollama service unchanged;
  the additional 16K alias remains available on the isolated server.


## November 12, 2026 — Publish navigation and evaluation results

- User requested GitHub publication of the latest work. GitHub master was still
  at a03c8e0; the local navigation checkpoint 43755d9 was not published.
- Publication includes that checkpoint's navigation/perception implementation,
  diagnostics and reports, plus the varied-goal evaluation runner, both November
  12 evaluation reports, README updates, and this progress log.
- All 47 offline regression tests passed again; whitespace checks passed.
  Source syntax was checked with python3 after the plain python command was
  unavailable. No new model inference or simulator evaluation was performed.
  Generated raw results, screenshots, models, environments, and secrets remain
  excluded.
- Uses the connected GitHub app and an expected-head, non-forced branch update.
  The publication commit includes this entry; historical statements that earlier
  tasks were uncommitted/unpublished describe their state at that time.

## November 12, 2026 — Interactive screenshot replay

- User requested an interactive view of every task step. Built a separate static
  Sites viewer at `/data/5pourghe/sites/household-agent-replay` from preserved
  November 12 results; no new model inference or simulator actions were run.
- Includes both official sanity tasks, all 15 assisted-start custom trials, and
  four original-start custom trials: 21 episodes, 104 decisions, including both
  failed custom episodes and every rejected/failed decision. Original screenshot
  bytes are retained and deduplicated into 101 PNG assets, with source-relative
  paths and SHA-256 hashes in `dist/evidence-manifest.json`.
- Custom decisions have before/after views. Official screenshots are explicitly
  pre-action captures; the next model-input image is labeled separately. No final
  official post-action screenshot exists, and none was fabricated or substituted.
- Added task/outcome filters, search, playback/speed controls, keyboard stepping,
  a full decision timeline, before/after comparison, expanded original images,
  recorded model outputs/prompts, execution and goal feedback, and trace downloads.
- Validation: all screenshot hashes and paths, episode/decision counts, failure
  counts, capture limitations, DOM references, and JavaScript syntax checked.
  DOM interaction checks exercised all 104 decisions, filtering/search, screenshot
  modes, playback, and final-view controls. The first test-harness attempt needed
  a strict-eval export correction; the corrected harness passed. Firefox visual
  preview failed due to the host's Snap namespace/home restriction, so rendered
  browser QA remains unverified. Data and interaction checks passed independently.
- Publishing tooling initially lacked Node; downloaded checksum-verified Node
  22.16.0 under the workspace. Source helper pushed the viewer source and packaged
  the matching archive. Private Sites deployment completed successfully:
  https://household-agent-replay.closedplatypus2.chatgpt.site
- Site ID: `appgprj_6af5aa69776c81919a04b035d32e52c5`; source commit:
  `eaddc2510bb69c425683b42bfe5b40098acc6c86`. Viewer source and assets are separate
  from the research GitHub repository; this progress entry remains a local change.


## November 12, 2026 — Investigate replay access failure

- User reported being unable to open the published replay. Sites reports the
  deployment active, not disabled, and restricted to the connected owner account
  alipourgheysari@gmail.com. A direct unauthenticated URL request returned HTTP
  403 with Cloudflare error 1010; this does not establish the user sees the same
  failure. Requested the displayed error to distinguish sign-in, edge blocking,
  and client rendering problems. Access settings were not changed.
- Created `/data/5pourghe/sites/household-agent-replay-offline.zip` containing
  the complete static viewer and screenshots, without hosting configuration.
  Extract and open `household-agent-replay/index.html`; no sign-in or server
  is needed. ZIP integrity and expected entry point checked.
- User clarified the symptom is a blank page. Browser-user-agent requests reach
  the site's private sign-in boundary (HTTP 401); the earlier Cloudflare 1010
  response was specific to the diagnostic request's non-browser user agent.
  Authenticated checks using the temporary Sites Bearer header returned HTTP 200
  for HTML, JavaScript, data, and CSS. Published JavaScript/data/CSS exactly match
  the validated local files; HTML differs only by an injected Cloudflare script.
  Deployment and missing source assets are therefore not demonstrated causes.
  The user's blank-page cause remains unconfirmed; private sign-in/browser
  interaction is a possible cause, not a verified diagnosis. Provided the offline
  ZIP as an alternative that does not depend on hosted authentication.


## November 12, 2026 — Progress review and proposed priorities

- Reviewed repository status, latest progress entries, README, and both November
  12 evaluation reports to answer the user’s progress/next-steps question.
  Git master tracks origin/master at e7b5248; existing local progress additions
  cover replay publication/access investigation. Offline replay ZIP exists.
- Confirmed recorded outcomes: official Qwen sanity 2/2 after the context fix;
  custom assisted starts 14/15 and default starts 3/4. These are distinct
  protocols and do not establish general reliability. No new tests, inference,
  simulator actions, or publication were performed during this review.
- Proposed priorities, not implemented: goal-consistent pickup and inventory
  recovery, collision/camera-limit handling and off-screen target search; then
  repeated held-out scene/object evaluation. Keep official baseline and custom
  agent comparisons separate; full benchmark and adapter remain outstanding.
- Hosted replay blank-page cause remains unresolved. The varied-goal report’s
  historical 0/2 sanity statement predates the subsequent official Qwen 2/2
  report; use the latter for current official baseline status.


## November 12, 2026 — Verify Bowl claim against raw pickup evidence

- User questioned the Bowl claim after seeing a successful Mug pickup. Checked
  original trial summaries, decision 03 simulator command/result, and subsequent
  feedback for mug_pickup_far_target_left_01 in the 092905 batch: PICKUP Bowl
  executed successfully; metadata records Bowl isPickedUp true and the goal Mug
  remained unpicked. Other three Mug trials succeeded. This claim concerns one
  specific failed trial, not every Mug episode. No new evaluation or code change.


## November 12, 2026 — Clarify AsgardBench versus custom action support

- Inspected the installed benchmark Action enum, model parser allowlist, PUT
  execution checks, and empty-hand helper, plus our custom executor/navigation.
- Official model parser accepts CLEAN, CLOSE, EMPTY, DRINK, FIND, OPEN, PICKUP,
  PUT, SLICE, SPRAY, TOGGLE_OFF, TOGGLE_ON. PUT is already supported by
  AsgardBench; EMPTY refers to liquid. EMPTY_HAND is an internal action, not in
  that parser allowlist. No model-facing DROP is listed; DropHandObject appears
  only in a commented-out workaround in the inspected scenario source.
- Our custom executor exposes OPEN/CLOSE/PICKUP/TOGGLE_ON/TOGGLE_OFF and primitive
  navigation, without PUT or DROP. Earlier recovery limitation applies to this
  custom loop, not a lack of PUT in AsgardBench. No implementation or run changes.


## November 12, 2026 — Make AsgardBench the main runner; park custom experiments

- User explicitly selected the official AsgardBench runner as the main workflow
  and requested the custom runner be put away with a durable explanation.
- Moved the custom household_agents package, 14 Python scripts, and six test
  modules into experimental/custom_runner/. Preserved the former README as
  USAGE.md, updated its command locations and links, and added a README recording
  origin, limitations, the reason for parking it, and explicit resumption guidance.
  Original custom sources are byte-identical apart from the model module's
  external-parser dependency path, adjusted for relocation with ASGARDBENCH_DIR
  override support. Generated outputs in the parked directory are ignored.
- Replaced the main README with official benchmark setup and usage. Added
  scripts/run_benchmark.py as a thin launcher of the unchanged external
  AsgardBench.Model.model_tester, defaulting to the official sanity suite and
  tested Qwen 16K alias. It preserves supplied endpoint/key settings, otherwise
  uses isolated local Ollama, creates fresh output roots, records launch metadata
  without credentials, forwards benchmark options/exit status, and supports
  preview via --dry-run. There is no custom-loop fallback.
- Added AGENTS.md instructions to use the official runner and leave custom work
  parked until explicitly requested. Existing reports, root results, source
  snapshots, and the separate replay viewer were not moved or rewritten.
- Validation: 47/47 existing offline regression tests passed after relocation;
  official runner CLI help passed without simulation/inference. Launcher checks
  passed for official delegation, forwarded arguments, environment/output
  isolation, exit-code propagation, refusal to reuse output roots, and dry-run
  without execution or directory creation. Python syntax, local documentation
  links, server-script shell syntax, and git diff --check passed. Independent
  byte comparison confirmed preservation of relocated sources.
- No new model requests, simulator episodes, full benchmark, model/server changes,
  commit, or publication. Benchmark checkout remains clean. Existing local
  progress-log additions were preserved. The next evaluation should use the
  official launcher; historical custom scores remain separately labeled.


## November 25, 2026 — Recover project status from local records

- Reviewed project instructions, README, latest progress entries, official sanity
  report, and local Git status to recover the stopping point for the user.
- Latest implementation remains the November 12 switch to official AsgardBench
  with custom work parked; launcher and relocation are still uncommitted locally.
  Recorded official baseline remains 2/2 after the context fix; no full benchmark
  is recorded. Replay hosted blank-page cause remains unresolved.
- No new tests, inference, simulator runs, commit, or publication performed.


## November 25, 2026 — Commit and publish the official-runner switch

- User authorized committing and pushing the pending runner switch to GitHub.
  Publication includes the official launcher, parked custom sources/tests and
  usage guide, workflow instructions, README, and accumulated progress entries.
- Rechecked all 47 existing offline regression tests: passed. Official launcher
  dry-run and Python syntax checks passed; each removed custom source/test has
  a preserved relocated counterpart, byte-identical except model.py's documented
  external dependency path adjustment. Whitespace checks passed.
- No model inference, simulator episode, full benchmark, or replay-site change.
  Publishing through the connected GitHub app with a non-forced expected-head
  update; remote success and local synchronization are verified after publication.
