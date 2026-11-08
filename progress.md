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

## Open issues and next work

- Reliability: schema-constrained output and bounded recovery are implemented
  and tested, but repeated model success and real physical-failure recovery remain
  unmeasured. Invalid responses are still checked rather than assumed impossible.
- Generalization: shared OPEN/CLOSE/PICKUP paths have live examples, but repeated
  runs and broader scenes/objects remain unmeasured. Successful formatting does
  not imply correct or feasible action choice.
- The full benchmark remains at the original **0/2** sanity result; the demo's
  workaround has not been integrated into the official benchmark path.
- Camera positioning is scripted; no autonomous navigation or general multi-step
  planner. Bounded retries may issue additional OPEN/CLOSE/PICKUP actions.
- Context retention and original full-format failure are not fully resolved.
- Shared Ollama installation/model/service configuration remain unchanged;
  upgrades require a separate decision rather than modifying a shared service
  as part of routine script work.
- GitHub shell authentication remains unavailable; publication uses the connected
  app. The earlier local/remote base mismatch was resolved during publication.
