# Action-pipeline diagnosis and verified TV improvement

The strongest reproducible finding is sensitivity to the action prompt and its
structured tracking context. On the same saved centred-TV image, Qwen selected
right with the rich tracking prompt and forward with a minimal prompt. The
original TV goal, action vocabulary, model, and schema were sufficient when the
context was simplified. This is evidence about this model/prompt interaction;
it does not explain the model's internal reasoning or identify one universally
bad JSON field.

The resulting optional minimal action prompt succeeded in all five fresh
three-step trials, versus 0/5 with the previous rich perception/action prompt.
It also succeeded once from the original default room start in 16 decisions.
All actions were model-selected and the TV power change was simulator-verified.

## Scope and method

Ran 68 saved-request probes without simulator execution:

- 33 Qwen probes covering context, goal wording, controls, image omission,
  conflicting location claims, simple text directions, exact-copy instructions,
  output contracts, sampling, and beginning/end replays.
- 24 Qwen probes removing individual tracking fields or adding a plain location
  sentence/range clarification.
- Two original-request replays after unloading Qwen. The centred replay started
  with an empty runtime; the second replay followed it in the same loaded model.
- Nine probes using the already installed LLaVA model and its existing server.

All 68 responses completed and passed their declared output contract. No
malformed responses, repair, transport retry, or direction substitution occurred.
Saved request/image hashes and actual raw responses were checked independently.

Qwen used the same 8B Instruct Q4_K_M digest as previous runs:
`70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb`,
on isolated Ollama 0.40.15. Except labeled sampling cases, options remained
temperature 0, top_p 1, num_ctx 16384, num_predict 1024. The model's runtime
reported repeat_penalty 1.0. The maximum Qwen prompt count in these batches was
1,526; runtime logs showed completed, untruncated requests.

## Main matched-image findings

The two images were the centred and left-side views from trial_01/decision_01
and decision_02 of `results/tv_selection_20261108T200722_257761Z/`. Each case used
the same source image and options, except for its named intervention. The left
view's source context contained the previous right turn; the centred view had
empty history. These are two related views, not a representative dataset.

| Qwen condition | Centred TV | TV on left |
| --- | --- | --- |
| Original rich tracking prompt | Right | Right |
| Remove tracking data and its instructions | Forward | Forward |
| Keep tracking data, remove tracking instruction paragraph | Right | Forward |
| Remove ordinary action history | Right | Left |
| Keep only navigation controls | Right | Right |
| Minimal prompt, goal “Turn on the TV” | Forward | Forward |
| Same minimal prompt, goal “Move closer to the TV” | Forward | Forward |
| Original rich prompt without image | Forward | Forward |
| Direction-question contract | CENTER + Forward | LEFT + Forward |
| End-of-batch original prompt replay | Right | Right |
| Original prompt after model unload/reload | Right | Right |

Simple text-only “target ahead/left/right” checks produced the expected forward,
left, and right actions. Exact-copy tests for forward and left also passed.
Thus action names and basic text direction mapping work in this model. Omitting
the image changes the rich prompt's output, so image input affects these choices;
this does not establish correct spatial interpretation or justify removing images
from a controller. Intentionally contradictory LEFT/RIGHT location claims on the
centred image produced right/left turns; these artificial conflicts were never
used to drive the simulator.

Goal wording alone did not distinguish the two minimal-prompt results. The earlier
eight-request study also found no change when native schema enforcement was
removed. Neither result supports schema enforcement or the final-goal wording
alone as the explanation for this stalled approach.

## Individual tracking fields

Removing `current` or `goal_interaction` changed the centred rich-prompt answer
to forward. Removing other individual fields, decision numbers, or adding a
range clarification retained right. A plain location sentence appended to the
nontracking prompt produced forward in the centred view. All corresponding
left-view field-sweep cases still chose right. This is strong prompt sensitivity,
not evidence of one consistently defective field or an application parse bug.

## Generation settings and comparison model

For the original centred rich prompt, temperature-only 0.7 probes at seeds
3407–3409 produced right, right, left. A profile using temperature 0.7, top_p 0.8,
top_k 20, repeat_penalty 1.0, and presence_penalty 1.5 produced the same three
actions. Runner logs confirmed those sampling values were received. No forward
choice occurred in these six probes. The profile follows the relevant generation
settings in [Qwen's published Instruct evaluation configuration](https://github.com/QwenLM/Qwen3-VL#evaluation-reproduction),
but changes several variables and does not reproduce their full evaluation.

LLaVA 7B on shared Ollama 0.6.2 selected forward on the centred rich prompt and
right on the left rich prompt. Its minimal prompts selected forward on both
images under both goal wordings, and its three text-direction checks passed.
This compares installed model/runtime stacks, not model weights alone. LLaVA
does not provide an across-the-board solution to the left-side rich-prompt case.

The services were initially idle. Models were unloaded sequentially using the
documented keep_alive behavior in the [Ollama API](https://docs.ollama.com/api/chat)
to avoid simultaneous GPU residency. The shared service's settings and model
files were unchanged. An immediate idle assertion after the old server's unload
acknowledgment failed because residency reporting was asynchronous; a follow-up
check confirmed the shared runtime was empty before further Qwen testing.

## Implemented candidate and live validation

Added reusable `minimal_goal_prompt` and the explicit `--action-prompt minimal`
option to both TV entry points. Existing standard prompts remain selectable and
are the default. The minimal variant supplies the current image, original goal,
legal controls, movement semantics, and a brief VLM-estimated target position.
It includes last-seen recovery, the latest validation/execution error, and active
repetition feedback when applicable. It omits the ordinary full tracking JSON
and successful-action history. The implemented generic wording says “target,”
where initial saved-image minimal probes said “TV”; exact live prompts are saved.

Location is still estimated by a separate image-only Qwen request. The same
schema, eligible action/object validator, parser/adapter, normal simulator
physics, bounded failures, and actual power-state check remain in place.

| Live check | Result | Model-selected sequence |
| --- | --- | --- |
| Same three-step fixture, five-decision cap, five fresh trials | 5/5 success | Forward, forward, forward, TV on |
| Original default room start, 40-decision cap, one episode | 1/1 success | 15 forward moves, TV on |

The controlled batch used the same model/server metadata, fixture hash, setup
pose, initial legal controls, and action cap as the failed rich-prompt batch.
No route, required move count, forced interaction, or scripted navigation was
supplied. Each trial's TV started off and ended on; power control became eligible
only for the final model decision. One matched initial RGB image was identical;
four pairs had small rendering differences (mean absolute channel differences
0.123–0.187 on a 0–255 scale). Saved-image ablations use exact pixels.

The farther episode used no setup actions or teleportation. Initial TV centre
distance was approximately 5.031 m; final centre distance was 1.945 m. Normal
interaction eligibility and actual power state establish success rather than a
centre-distance threshold. This remains the direct AI2-THOR demo: it does not
enforce AsgardBench's separate holding-a-remote scenario rule.

All 47 existing regression tests passed after the optional prompt integration.
This is a demonstrated improvement on these starts, not proof of reliable
obstacle avoidance, live recovery after collisions, other scenes or objects,
or arbitrary autonomous navigation. The exact internal reason for the rich
context's right-turn bias remains unknown. No larger model, new model download,
runtime update, or permanent generation-setting change was required.

## Artifacts and reuse

Probe runner: `scripts/diagnose_action_pipeline.py`. Pass saved decision folders;
`--tracking-fields` performs the field sweep, `--case` filters named probes,
and `--model`/`--base-url` label a different installed stack explicitly.

- Broad Qwen probes: `results/action_pipeline_diagnosis_20261108T205700_491107Z/`.
- Field sweep: `results/action_pipeline_diagnosis_20261108T205844_952783Z/`.
- Cold replay: `results/action_pipeline_diagnosis_20261108T205952_485360Z/`.
- LLaVA comparison: `results/action_pipeline_diagnosis_20261108T210039_763623Z/`.
- Five successful trials: `results/tv_selection_20261108T210200_939530Z/`, with
  verification.json, all decision traces, before/middle/after screenshots, and
  a representative complete sequence.html gallery.
- Default-start success: `results/tv_goal_20261108T210329_321491Z/`, with the
  same evidence and a 17-frame sequence.html gallery.

Generated artifacts and model metadata remain ignored by Git. No commit or push
was performed.
