# Varied goals and starting positions — November 12, 2026

## Protocol

User requested tests beyond the successful TV pose. The first batch contains
15 fresh-scene episodes: five task/scene cases, each from three distinct physical
starting positions. Each episode has 20 action decisions, at most three consecutive
failures, and the existing state-aware repetition recovery. Failed episodes were
retained; no episode was rerun or replaced and no prompt/model change was made.

All runs use Qwen3-VL 8B Instruct (Q4_K_M, digest starting `70e58e37beb1`),
Ollama 0.40.15 on localhost:11435, the minimal action prompt, and the separate
image-only target locator. Inference settings remain context 16,384, output
allowance 1,024, temperature 0, top_p 1. The screenshot used by perception and
action selection is byte-identical at each decision. All normal navigation and
OPEN/CLOSE/PICKUP/TOGGLE controls remain available when eligible. Goal success
requires the actual bound object's state, including inventory membership for pickup.

Initial placement is assisted in the first batch. A deterministic ranking of
reachable positions selects a nearby eligible view and two farther, angled,
initially ineligible views with at least 40 rendered target pixels. Normal
simulator interactions establish an unfinished initial state if required (for
example, opening the fridge before a CLOSE goal). Setup coordinates, instance
labels, paths, and movement counts are not supplied to the model. View names
refer to intended setup geometry; they are not ground-truth perception labels.
These are direct AI2-THOR rules, not the official benchmark's scenario rules.

## Controlled starting-view results

All 15 setups succeeded. **14/15 episodes reached their goal**, including
**9/10 farther starts**. Thirteen episodes completed with no decision errors;
one succeeded after repetition recovery and one failed. This describes single
trials of different conditions, not a reliable population success-rate estimate.

Numbers below are action decisions, including rejected proposals.

| Task | Scene | Near | Far, target left | Far, target right |
|---|---|---|---|---|
| Turn on TV | FloorPlan201 | Success, 1 | Success, 2 | Success, 3 |
| Turn on TV | FloorPlan202 | Success, 1 | Success, 13 | Success, 2 |
| Open fridge | FloorPlan1 | Success, 1 | Success, 2 | Success, 3 |
| Close fridge | FloorPlan1 | Success, 1 | Success, 2 | Success, 2 |
| Pick up mug | FloorPlan1 | Success, 1 | **Failure, 14** | Success, 4 |

The left-angle TV start in FloorPlan202 produced repeated right/left turns.
Two repetition-limit rejections elicited forward movement, and the model
ultimately switched on the correct TV. Its success depends on the existing
recovery mechanism; it was not an error-free trajectory.

The left-angle mug trial exposed several problems. The model proposed
`PICKUP Cabinet`, which was rejected by application validation: Cabinet was not
an eligible pickup object. It then picked up a **Bowl**, not the target Mug.
Three subsequent forward commands were rejected by the simulator because the
kitchen island blocked movement. The agent cycled between turns and forward
movement and stopped at the repetition limit after two further rejected
proposals. The Mug remained unpicked. The action set has no PUT/DROP operation,
so recovering from the wrong pickup is also limited by the full inventory.
The other two mug trials verified the Mug in inventory and its pickup state.

The first batch contains 52 decisions and 104 model requests (52 location,
52 action), all ending normally. There were 47 executed commands, one rejected
invalid action/object pair, three simulator collision errors, and four
repetition rejections across two episodes. Twelve actual yaw changes matched
the requested ±45-degree turns. Raw responses, legal choices, parsed actions,
commands, screenshots, initial conditions, and final states were independently
checked; `verification.json` records the checks.

Artifacts: `results/goal_evaluation_20261112T092905_544359Z/` contains
`summary.json`, `verification.json`, `overview.html`, source snapshots/hashes,
a local verification helper, and every setup and decision trace.

## Default room starts

A separate four-episode follow-up uses each room's original pose and object
state without any setup actions: TV in FloorPlan201/202, fridge OPEN, and Mug
PICKUP in FloorPlan1. Same model, prompt, controls, recovery, and 20-decision cap.
Fridge CLOSE is excluded because the default fridge is already closed.
**3/4 default-start episodes succeeded.** All four initial states and original
poses were accepted without setup commands; these are not additional assisted
camera placements.

| Task | Scene | Outcome | Decisions | Decision errors |
|---|---|---|---|---|
| Turn on TV | FloorPlan201 | Success | 16 | None |
| Turn on TV | FloorPlan202 | **Failure: decision limit** | 20 | One repetition rejection |
| Open fridge | FloorPlan1 | Success | 1 | None |
| Pick up mug | FloorPlan1 | Success after feedback | 8 | Two camera-limit errors |

FloorPlan201 repeated the earlier TV result: 15 model-selected forward moves
and then TV power-on, from a reported target-center distance of 5.031 m.
FloorPlan202 picked up a RemoteControl, moved/looked around, and exhausted its
20-decision budget with the TV still off. Its final reported target-center
distance was 2.963 m versus 2.597 m initially. No direction correction or
replacement trial was used. The final screenshot shows the held remote in front
of curtains, with the TV off-screen.

The default-start Mug trial initially reported NOT_VISIBLE and selected
LOOK_DOWN repeatedly. After two simulator rejections for attempting to look
below the 60-degree limit, it selected ROTATE_LEFT, two forward moves, and
PICKUP Mug. Final metadata and inventory confirm the intended Mug was picked up.
This is recovery after real execution errors, not an error-free first attempt.
The default fridge was already interactable and therefore its one-action
success is an interaction check, not a navigation success.

The follow-up contains 45 decisions, 90 requests, 44 executed commands, one
repetition rejection, and two camera-limit execution errors. All requests ended
normally; the model/runtime identity was unchanged at the end. Independent
verification checks the empty setup-action lists, input hashes/options, raw
choices, command mappings, and final states.

Artifacts: `results/goal_evaluation_20261112T093427_664213Z/`, including
`summary.json`, `verification.json`, `runtime_identity_end.json`, `overview.html`,
source snapshots/hashes, verification helper, and all decision traces.

## Interpretation

Across both batches, **17/19 episodes succeeded**: 15 without any decision
errors, two after recovery, and two failures. The batches have different
starting-condition protocols, so the combined fraction is descriptive only.
There were no setup failures or automatic trial reruns. All 194 requests were
checked for identical inference settings and correct screenshot hashes.

The minimal prompt extends beyond one TV pose to another room and OPEN,
CLOSE, and PICKUP goals. It still makes wrong-object choices, struggles with
obstacles and missing targets, and can waste actions on camera or movement
loops. Before treating the agent as reliable, evaluate independent additional
rooms/objects and address goal-consistent selection, inventory recovery,
collision avoidance, and camera-limit awareness. None of these fixes was
implemented during this evaluation.

All 47 existing offline regression tests passed. Script syntax, CLI help,
documentation links, and `git diff --check` passed. Representative failure and
successful-pickup screenshots were visually inspected.

## Reproduction and limits

The two commands are documented in README.md under “Evaluate different tasks
and starting views.” `scripts/evaluate_goals.py` supports selecting conditions
and additional repeats. It snapshots the executed source per batch and saves
incremental summaries so errors are not lost.

This evaluation tests three rooms, three object types, and four operations.
One episode per condition and simulator-selected initial target visibility in
the first batch limit generalization. Most successful farther episodes need
only one to three forward moves; they do not establish obstacle avoidance,
long-horizon planning, hidden-object search, or robust recovery. The full
AsgardBench sanity result remains unchanged at its original 0/2; no training
or official benchmark integration was performed.
