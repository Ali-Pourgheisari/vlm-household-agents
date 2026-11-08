# Ollama/LLaVA action-output investigation

Date: November 1, 2026, Europe/Berlin. External AsgardBench revision:
`4d38d380362d767893611fc160dc78665d1356b8`. Server: Ollama 0.6.2.
Model: `llava:7b`, digest `8dd30f6b0cb19f555f2c7a7ebda861449ea2cc76bf1f44e262931f45fc81d081`.

## Archive status

This report preserves the November 1 investigation. The one-off diagnostic
scripts described below were removed during repository cleanup because they
depended on local, ignored experiment artifacts. Script names and settings below
document the original experiments; they are not current runnable entry points.
Generated results remain local and are not included in Git.

## Outcome and scope

A project-local custom diagnostic now returns `Action: OPEN Fridge`, accepted
by AsgardBench's unchanged action parser. The tested workaround uses native
`/api/chat`, explicit context 16384, `num_predict=1024`, temperature 0, top_p 1,
combined text and image in one native user message, and a short final output
contract limiting the format and object vocabulary.

This is one successful formatting/task-choice sample. It does not establish
simulator feasibility, independent planning, full input retention, benchmark
success, or a complete repair of the external benchmark. The external benchmark,
shared Ollama installation, stored model, and service configuration were not
changed. No simulator actions or benchmark evaluation were run during this investigation.

The investigation found several distinguishable failure layers. A single claim
that LLaVA ignores system messages does not explain all observations.

## What was already verified

The original full prompt has 18,390 static characters and 759 dynamic characters;
combining them with two newlines yields 19,151 characters. Its 3,047 whitespace
words are not a token count. The task is `Open the fridge.`; the custom available
object vocabulary is only `Fridge`, not a simulator-derived inventory.

The original A/B requests contain identical static/dynamic text in the same
order and the same image bytes, except B inserts two newlines at the removed
message boundary. Both contain the required `Action: $ACTION $OBJECT` instruction.
The screenshot is the existing external `environment_test/01_before.png`,
SHA-256 `f71f5d92c0256c847cfd44371085062a1081247927566221b9d4b333408ccb77`.

The model advertises 32768 context positions. That is model metadata, distinct
from the runner's allocated per-sequence context and available memory.

## Failure layer 1: request compatibility and context handling

The version-pinned [OpenAI adapter](https://github.com/ollama/ollama/blob/v0.6.2/openai/openai.go)
accepts `max_tokens` and maps it to native `num_predict`. It does not define
`max_completion_tokens` or per-request `num_ctx`. The saved 8192 completion
limit was requested by the original script, but was not enforced by this
adapter. That finding does not itself explain the initial scene descriptions.

The adapter converts each text or image content part into a separate native
message. Consequently, effective layouts are:

- A adapter: system static text, user dynamic text, user image-only.
- B adapter: user combined text, user image-only.
- B colocated: one native user message containing combined text and image.

The [chat prompt builder](https://github.com/ollama/ollama/blob/v0.6.2/server/prompt.go)
checks message fit against `num_ctx`, always retains the final message, and
collects system messages. For these adapter layouts the final message is
image-only. This creates a source-supported mechanism by which earlier user
text can be dropped when it does not fit. The CLIP fitting allowance is 768
positions per image; it is not a measurement of actual image embeddings.
The [runner](https://github.com/ollama/ollama/blob/v0.6.2/runner/llamarunner/runner.go)
also has an input-truncation path after image expansion.

These mechanisms are consistent with the low-context descriptions and unequal
usage counts. No runtime retained-token trace or direct truncation log was
accessible, so the exact text dropped in a particular request is not confirmed.
Do not infer complete retention at 16384 from usage counts alone.

The [template code](https://github.com/ollama/ollama/blob/v0.6.2/template/template.go)
merges consecutive same-role messages during rendering, but message-fit
selection occurs before final rendering. Thus identical client text does not
ensure identical retained input. There is no established need to change the
stored model template, and it was left unchanged.

## Failure layer 2: the output allowance ends before the action

The unmodified full prompt asks for visual observations, inventory, previous
action assessment, double check, plan reasoning, memories, a suggested action
sequence, and finally an Action line. In the preceding four-request experiment,
16384-context responses exhausted 256 output tokens before reaching that line.
Both had `done_reason=length`; these were output-limit failures, not completed
responses omitting a final action.

Raising only the output allowance to 1024 for the corresponding high-context
A/B adapter cases produced normal `stop` responses with final action lines at
435 and 428 completion tokens. Increasing the output limit at context 2048 did
not resolve the scene-description behavior.

## Failure layer 3: an Action line can still be invalid

With enough output allowance, the original full-format responses chose
`FIND Refrigerator` or `FIND Knife`. Both are invalid under this diagnostic's
available-object list, which contains only `Fridge`. Another response emitted
`Action: Approach the fridge`, which fails the parser's uppercase action syntax.
The parser was correctly rejecting invalid outputs; it was not merely failing
to recognize a valid `OPEN Fridge` response. No synonym rewriting or action
substitution was added. Some generated plans also invented unsupported steps,
so structured output alone is not evidence of sound planning.

## New controlled requests

Seven new inference requests were made in this investigation: six predeclared
context/layout cases and one subsequent output-contract case. Every request
was attempted once, succeeded with HTTP 200, and had no automatic retry.
All used the same source prompt/image, temperature 0, top_p 1, num_predict 1024,
stream false, keep_alive 2m, timeout 600 seconds. Only the last case changes
prompt text by appending the explicitly documented output contract.

| Case | Per-sequence context | Prompt/completion usage | Termination | Final output | Parser |
| --- | ---: | ---: | --- | --- | --- |
| A adapter | 2048 | 2048 / 180 | stop | Scene description, no Action | Rejected |
| B adapter | 2048 | 586 / 126 | stop | Scene description, no Action | Rejected |
| B colocated | 2048 | 2048 / 247 | stop | `Action: Approach the fridge` | Rejected |
| A adapter | 16384 | 6698 / 435 | stop | `Action: FIND Refrigerator` | Invalid object |
| B adapter | 16384 | 6699 / 428 | stop | `Action: FIND Knife` | Invalid object |
| B colocated | 16384 | 6697 / 310 | stop | `Action: FIND Refrigerator` | Invalid object |
| B colocated + final contract | 16384 | 6828 / 8 | stop | `Action: OPEN Fridge` | Accepted |

Colocation is an additional rendering change: this version prefixes image tags
within their native message, so the colocated variant places the image marker
before the full text, while adapter variants place it after text in a separate
message. The colocation comparisons do not isolate grouping independently of
image-marker position. All text ordering and image bytes remain unchanged.

Runtime arguments were captured before and after every new request. The low
cases used total `--ctx-size 8192 --parallel 4`, or 2048 positions per slot;
the high cases used `--ctx-size 16384 --parallel 1`, or 16384 per slot. The
[cache implementation](https://github.com/ollama/ollama/blob/v0.6.2/runner/llamarunner/cache.go)
provides that division. Four configured slots do not imply four active clients.
The output-contract case had the same high-context runner before and after.

Preflight found no loaded model for the six-case run. No unrelated established
endpoint connections were observed in pre/post snapshots. Intervening shared
requests cannot be excluded; no other workload was stopped or modified.
The visible journal reported no entries and explicitly warned of restricted
access to other users/system messages. No direct input-truncation log was
obtained. This remains an evidence limitation, not proof that truncation was
absent. Exact matching local tokenization was not established.

## Implemented workaround

`scripts/diagnose_action_output.py` reuses the saved full renderer output and
external parser. It uses native request options supported by the installed
version. Its optional `high_B_contract` case appends:

> FINAL OUTPUT CONTRACT FOR THIS CUSTOM DIAGNOSTIC: Use this contract instead of
> the earlier verbose response format. Return exactly one line: Action: ACTION
> OBJECT. Choose ACTION from CLEAN, CLOSE, EMPTY, DRINK, FIND, OPEN, PICKUP, PUT,
> SLICE, SPRAY, TOGGLE_OFF, TOGGLE_ON. The only allowed OBJECT identifier is
> Fridge (exact spelling). Choose the next action for the current task using
> the current image. Objects and tasks in the examples are not the current task.

The contract gives the legal action vocabulary and object identifier, not the
answer `Action: OPEN Fridge`. The raw response was ` Action: OPEN Fridge `,
`done_reason=stop`, with 8 completion tokens. AsgardBench parsed action `OPEN`,
object `Fridge`, and no error. This is a prompt-format modification for a custom
diagnostic, not an unchanged official benchmark prompt or a trained improvement.

The working case used the `high_B_contract` option of the former
`scripts/diagnose_action_output.py`. Its settings and exact output contract are
recorded above. For future tasks, the allowed object vocabulary must come from
the actual task context rather than reuse this diagnostic's restricted `Fridge`
list. The diagnostic did not execute returned actions.

## Artifacts, validation, and remaining work

- Original placement artifacts: `results/message_placement_20261101T080400_762672Z/`.
- Previous four-request context run: `results/context_control_20261101T082120_017284Z/`.
- New six-case matrix: `results/action_output_20261101T082542_286389Z/`.
- Accepted contract case: `results/action_output_20261101T082642_535422Z/`.

Each new directory includes sanitized native requests, full raw responses,
response text, parser errors/actions, token usage, finish reasons, source prompt,
image provenance, executed script, and pre/post runtime snapshots. Credentials
and base64 image payloads are excluded. Generated results remain gitignored.
The script's offline checks verify source text, image SHA-256, request variants,
raw/result agreement and single-attempt execution. The benchmark parser also
rejects the observed invalid examples when replayed offline.

The original benchmark path is still external and unmodified; it has not been
wired to the workaround. The complete full-format benchmark behavior remains
unresolved. Additional tasks, state-dependent action feasibility, reliable
format adherence across repetitions, and end-to-end simulator performance
require separately scoped validation. The present work establishes a practical
custom-request workaround and identifies compatibility, context dependence,
output truncation, and vocabulary adherence as separate issues.
