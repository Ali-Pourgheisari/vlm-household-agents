# Qwen direction diagnostic using existing TV screenshots

On November 8, 2026, Qwen3-VL 8B Instruct correctly classified the TV's horizontal
position in **11/12 existing screenshots**. It recommended moving forward in all
three centred views, moving backward in all three left-edge views, and no movement
in the six views where the TV was absent. In one absent-target view, it falsely
reported a TV on the left while still recommending no movement.

## Method

- Used trial_01 from the original three-step test
  (`results/tv_selection_20261108T175446_300090Z/`) and assisted-feedback test
  (`results/tv_selection_20261108T184147_550638Z/`). Each contributed its initial
  image and five post-action images. Original image bytes were preserved.
- Ran `scripts/diagnose_direction.py` against isolated Ollama 0.40.15 on port
  11435, using qwen3-vl:8b-instruct, Q4_K_M, digest
  `70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb`.
- Each request contained one image and the same diagnostic prompt, with no
  history, simulator labels, object IDs, positions, range information, or route.
  Reference labels were added separately after inference.
- Asked for target_position (LEFT/CENTER/RIGHT by horizontal image thirds,
  NOT_VISIBLE, or UNCERTAIN) and next_movement (six navigation controls or NONE).
  The prompt requested NONE for an absent or uncertain target. No object
  interaction controls were offered. All responses used a two-field JSON schema.
- Options: temperature 0, top_p 1, num_ctx 16384, num_predict 1024; independent
  user messages, no retries. All 12 responses finished normally and validated.
  The simulator was not launched and no proposed movement was executed.

## Per-image answers

Reference positions come from inspection of the images and recorded camera
sequence. They were not supplied to the model.

| Image | Saved view | Reference TV position | Qwen position | Qwen movement |
| --- | --- | --- | --- | --- |
| 1 | Original: start | CENTER | CENTER | MOVE_AHEAD |
| 2 | Original: after forward | CENTER | CENTER | MOVE_AHEAD |
| 3 | Original: after first right | LEFT | LEFT | MOVE_BACK |
| 4 | Original: after second right | NOT_VISIBLE | NOT_VISIBLE | NONE |
| 5 | Original: after sideways forward | NOT_VISIBLE | NOT_VISIBLE | NONE |
| 6 | Original: after left | LEFT | LEFT | MOVE_BACK |
| 7 | Assisted: start | CENTER | CENTER | MOVE_AHEAD |
| 8 | Assisted: after right 1 | LEFT | LEFT | MOVE_BACK |
| 9 | Assisted: after right 2 | NOT_VISIBLE | NOT_VISIBLE | NONE |
| 10 | Assisted: after right 3 | NOT_VISIBLE | NOT_VISIBLE | NONE |
| 11 | Assisted: after right 4 | NOT_VISIBLE | LEFT | NONE |
| 12 | Assisted: after right 5 | NOT_VISIBLE | NOT_VISIBLE | NONE |

## Interpretation and limits

Qwen can usually locate the TV when directly asked in this selected image set.
For the initial views, moving forward agrees with the independently verified
calibration. The diagnostic also recommends forward for the exact assisted-test
initial image on which the original episode selected a right turn. The same
pixels can therefore produce different movement proposals under different task
prompts and output protocols.

For left-edge TV views, moving backward does not turn the camera toward the
target; a left turn would align the view. A backward move could be part of an
obstacle-avoidance plan, so these unexecuted proposals do not establish physical
failure. The diagnostic contains no multi-step plan or simulator feedback that
would verify such an interpretation. The false TV detection in image 11 shows
that recognition also remains imperfect.

These are 12 related images from one scene, including similar views, with no
right-side TV example. The fraction 11/12 is descriptive, not a general accuracy
estimate. Compared with the live episode, the task changed from turning on the
TV to approaching it; history, eligible controls, output fields, and available
NONE response also changed. This is evidence of prompt-sensitive proposals,
not proof that one prompt change fixes navigation or completes the TV goal.

## Local artifacts

`results/direction_diagnostic_20261108T194208_867086Z/` contains:

- `report.html`: original screenshots beside each answer and reference label.
- `evaluation.json`: per-image reference labels and descriptive counts.
- `summary.json`: source paths, image hashes, predictions, usage, model metadata.
- `prompt.txt`, the executed script snapshot, and per-image original PNGs,
  sanitized requests, raw responses, and validation results.

Image-hash checks confirmed that copied inputs match both their original files
and the requests' recorded hashes. Generated artifacts remain ignored by Git.
