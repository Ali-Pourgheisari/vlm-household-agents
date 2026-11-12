# Official AsgardBench sanity baseline with Qwen — November 12, 2026

The completed Qwen baseline passed **2/2 official sanity tasks**, after correcting
an initial runtime-context launch failure. The benchmark source, task definitions,
prompt, parser, execution rules, and decision limits were unchanged. This tests
Qwen through AsgardBench's existing actor; it does not integrate our custom agent.

## Completed evaluation

| Task | Result | Model-selected high-level actions |
| --- | --- | --- |
| FloorPlan202: turn on TV | Pass, 4 actions | FIND RemoteControl → PICKUP RemoteControl → FIND TVStand → TOGGLE_ON Television |
| FloorPlan203: turn on TV | Pass, 3 actions | FIND RemoteControl → PICKUP RemoteControl → TOGGLE_ON Television |

All seven responses parsed successfully and all seven high-level actions
succeeded. The saved observations confirm a held RemoteControl before each TV
toggle. The live benchmark goal evaluator reported each television's actual
`isToggled == True`. Neither task required an extension or reported an API,
invalid-response, invalid-action, invalid-object, or execution error. One episode
was run per task after the context correction; failed episodes were not rerun.
The completed evaluation took approximately 2 minutes 15 seconds.

AsgardBench provides high-level actions such as FIND, and its executor handles
object-facing/positioning and related subactions. These seven actions are not
seven primitive camera/movement commands. Consequently, this result measures
success under the benchmark's action abstraction, not independent low-level
navigation. The benchmark's TV rule requiring a held remote remained enabled.

## Runtime and launch failure

- Benchmark commit: `4d38d380362d767893611fc160dc78665d1356b8`.
- Isolated local Ollama: `0.40.15`, endpoint `http://127.0.0.1:11435/v1`.
- Original model: `qwen3-vl:8b-instruct`, Q4_K_M, digest
  `70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb`.
- The first launch used the original model with a default 4,096-token allocation.
  Ollama rejected the initial 5,804-token request with HTTP 400 before an action
  could execute. The official result formatter then divided by zero for a
  zero-step episode and the process exited 1. The second task was not attempted.
  This aborted launch is retained separately and is not a completed 0/2 result.
- Created local alias `qwen3-vl:8b-instruct-sanity-ctx16k` with only
  `num_ctx=16384` added. Alias digest:
  `8fd9b24e4c1ff55a83f5559d11f50fba97b5412917792157b675a78edd931a74`.
  Verified identical model/projector weight blobs, template, capabilities, and
  prior parameters. No model download, training, or original-model replacement.
- Active runtime metadata confirmed context 16,384. Benchmark defaults were
  preserved: temperature 0, output cap 8,192, image mode, previous color image,
  simple feedback, memory, full-plan response, and prompt v2. Remaining sampling
  defaults were inherited unchanged from the installed model.
- The older LLaVA 0/2 result remains historical evidence. This comparison changes
  both model/runtime stack and context allocation, so it cannot isolate a single
  cause of improvement.

## Evidence and verification

Local ignored bundles, relative to the project root:

- Aborted launch: `results/asgard_sanity_qwen_20261112T095511_346796Z/`.
- Completed evaluation:
  `results/asgard_sanity_qwen_ctx16k_20261112T095624_651245Z/`.

The completed bundle contains `manifest.json`, `model_metadata.json`, benchmark
Python/task snapshots and SHA-256 hashes, `console.log`, process exit metadata,
final server identity/model metadata, official config/results JSON, and per-task
plans, screenshots, raw model response text, and step logs. `overview.html`
provides the pre-action screenshots and responses; it does not claim to show
post-action screenshots. `verification.json` records the verification checks.

Verification independently reparsed all seven stored model responses with the
unchanged AsgardBench parser and matched each action/object to the saved executed
step. Checked success flags, remote-holding observations, both live goal-check
messages, result counts, source/snapshot hashes, model alias equivalence, runtime
context, and process exit 0. No reported API errors or retries occurred in the
completed run. Full HTTP response envelopes and token usage are not captured by
the unchanged actor; saved model responses are the returned text.

The initial post-run clean-tree assertion found the benchmark's tracked
`AsgardBench/Data/placement_cache.json` had changed during execution. Preserved its
generated contents and diff in the bundle, then restored the original from the
initially clean checkout. The initial failed verification is retained as
`verification_before_cache_cleanup.json`; all final checks pass and the benchmark
checkout is clean. No benchmark source or task modifications were needed.

## Reproduction

With the isolated server running and the original Qwen model installed, create
the separate context alias once:

```bash
curl http://127.0.0.1:11435/api/create \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-vl:8b-instruct-sanity-ctx16k","from":"qwen3-vl:8b-instruct","parameters":{"num_ctx":16384},"stream":false}'
```

Choose a new output directory for every run to preserve earlier trials:

```bash
cd /data/5pourghe/AsgardBench
ASGARDBENCH_TEST_DIR=/data/5pourghe/vlm-household-agents/results/NEW_RUN/Test \
OPENAI_BASE_URL=http://127.0.0.1:11435/v1 OPENAI_API_KEY=ollama \
OPENAI_CACHE_CONTROL=automatic \
xvfb-run -a uv run --no-sync python -m AsgardBench.Model.model_tester \
  --test magt_benchmark_sanity --model qwen3-vl:8b-instruct-sanity-ctx16k
```

This result establishes that the current Qwen/runtime setup can complete these
two official tasks. It does not establish broader reliability or a full benchmark
score. The full benchmark and the proposed custom-agent adapter were not run or
implemented. No commit or publication was performed.
