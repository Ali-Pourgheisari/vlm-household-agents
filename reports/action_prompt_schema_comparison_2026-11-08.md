# TV action prompt/schema comparison

On November 8, 2026, eight independent saved-image requests compared the current
action prompt with a shorter prompt, each with and without Ollama schema
enforcement. Removing the schema did not change any paired answer. Shortening
the prompt changed the left-side TV answer from right turn to forward movement;
the centred-TV answer remained a right turn in every condition.

## Results

| Prompt | Schema enforcement | TV centred | TV on left |
| --- | --- | --- | --- |
| Current | On | ROTATE_RIGHT | ROTATE_RIGHT |
| Current | Off | ROTATE_RIGHT | ROTATE_RIGHT |
| Short | On | ROTATE_RIGHT | MOVE_AHEAD |
| Short | Off | ROTATE_RIGHT | MOVE_AHEAD |

All eight raw outputs were complete, valid two-field action/object JSON and
passed the existing eligible-pair validator. There were no malformed responses,
transport errors, repairs, or retries. No actions were executed.

## Controls

- Images and requests came from trial_01/decision_01 (TV centred) and decision_02
  (TV left) in `results/tv_selection_20261108T200722_257761Z/`.
- The current/schema condition reproduced the saved request exactly, including
  the image bytes, prompt, model, schema, options, stream setting, and keep-alive.
- Within each prompt pair, the only changed request field was removal of
  `format`. The unconstrained condition did not use `format: "json"` or a new
  schema. The prompt still requested JSON and the original action/object fields.
- The shorter prompt retained the same goal (Turn on the TV), exact eligible
  controls, movement semantics, and factual feedback: location estimate,
  previous/last-seen locations, phase, goal-interaction availability, goal
  status, and observed history. It compressed instructional wording and
  reformatted feedback. It did not introduce a route or directional answer.
- Each request contained one user message with one original image, without
  conversation messages. The left-view factual feedback retained the original
  previous-action history in every condition for that image.
- Used Qwen3-VL 8B Instruct Q4_K_M, digest
  `70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb`,
  on isolated Ollama 0.40.15 at port 11435. Both identity checks matched the saved
  live experiment before inference.
- Options were unchanged: temperature 0, top_p 1, num_ctx 16384,
  num_predict 1024, stream false, keep_alive 2m. Condition order was reversed
  for the second image to reduce a fixed order confound.

## Interpretation and limits

In these four matched prompt/view pairs, schema enforcement did not explain the
right-turn behavior. This does not rule out schema effects on other inputs or
other generation settings. The prompt variant affected one image, establishing
sensitivity to wording/formatting in this small comparison. The two prompt
versions also differ in instruction detail, so this is not a pure token-length
test and does not isolate one sentence as causal.

The failed initial approach remains unresolved: a centred TV still produced a
right turn in all four conditions. Forward movement on the left-side image was
not executed or checked for collision, alignment, or eventual task completion.
There is no new simulator success claim. These are two related views from one
scene, one request per condition, at temperature zero, without a right-side or
off-screen test. The broader model-versus-interface cause remains open.

## Reproduction and artifacts

Run with existing decision directories:

```bash
uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B scripts/compare_action_requests.py \
  results/tv_selection_20261108T200722_257761Z/trial_01/decision_01 \
  results/tv_selection_20261108T200722_257761Z/trial_01/decision_02
```

The original comparison is saved in
`results/action_request_comparison_20261108T204657_782271Z/`: report.html,
verification.json, summary.json, executed source snapshot, original inputs and
feedback, exact prompts, sanitized requests/image hashes, raw responses, and
validation results. Generated results remain ignored by Git.
