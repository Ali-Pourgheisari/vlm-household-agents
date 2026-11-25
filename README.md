# VLM Household Agents

This project evaluates vision-language models on household tasks using
**AsgardBench as the main runner**, with AI2-THOR as the simulator.
Authors: Ali Pourgheisari and Mehran Rajabi. Work in progress.

```text
AsgardBench task + prompt + screenshot
                  ↓
          VLM via model endpoint
                  ↓
AsgardBench parser, executor, and scenario rules
                  ↓
       AI2-THOR action and feedback
                  ↓
       AsgardBench goal evaluation
```

Use the official benchmark's actions, including FIND and PUT, and its existing
execution assistance and rules. The launcher below delegates directly to
`AsgardBench.Model.model_tester`; it does not implement another agent loop.

## Setup

AsgardBench remains an external dependency, expected beside this repository:

```text
/data/5pourghe/
├── AsgardBench/
└── vlm-household-agents/
```

The reference benchmark revision is recorded in
[asgardbench-commit.txt](asgardbench-commit.txt). For a new checkout:

```bash
cd /data/5pourghe
git clone https://github.com/microsoft/AsgardBench.git
cd AsgardBench
git checkout "$(cat ../vlm-household-agents/asgardbench-commit.txt)"
uv sync
```

The launcher needs Python 3, `uv`, and `xvfb-run`. It uses AsgardBench's own
environment. Set `ASGARDBENCH_DIR` or `--benchmark-dir` for another checkout.

## Main command: official sanity evaluation

The current local setup uses Qwen3-VL 8B Instruct through an isolated Ollama
0.40.15 server on port 11435. Runtime/model files are outside this repository.
If that server is stopped, start it in another terminal:

```bash
cd /data/5pourghe/vlm-household-agents
bash scripts/serve_qwen.sh
```

The official prompt exceeded the original 4K context. The tested model alias
`qwen3-vl:8b-instruct-sanity-ctx16k` uses the same weights with a 16K context.
If that alias is absent, create it against the isolated server:

```bash
curl http://127.0.0.1:11435/api/create \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-vl:8b-instruct-sanity-ctx16k","from":"qwen3-vl:8b-instruct","parameters":{"num_ctx":16384},"stream":false}'
```

Preview the command, then launch a new evaluation:

```bash
python3 scripts/run_benchmark.py --dry-run
python3 scripts/run_benchmark.py
```

Defaults are the official two-task `magt_benchmark_sanity` suite and the tested
Qwen alias. Every launch creates a fresh output root under `results/official_*`
to preserve earlier runs. `--output-dir` selects a different new output root.
There is no automatic rerun or fallback to our custom runner.

For another model/endpoint, set `OPENAI_BASE_URL` and `OPENAI_API_KEY` and pass
`--model`. With neither variable set, the launcher defaults to the local endpoint
`http://127.0.0.1:11435/v1` and the local key `ollama`. Existing values are retained.
Additional arguments, such as `--rep 2`, pass through to the official runner.
Use its own help to inspect benchmark configuration:

```bash
cd /data/5pourghe/AsgardBench
uv run --no-sync python -m AsgardBench.Model.model_tester --help
```

The full benchmark is an explicit choice:

```bash
python3 scripts/run_benchmark.py --test magt_benchmark --dry-run
# Remove --dry-run when intentionally starting the full evaluation.
```

## Custom runner: parked for future experiments

The former direct-AI2-THOR runner, scripts, and tests live in
[experimental/custom_runner/](experimental/custom_runner/README.md). It is
inactive for normal work. It was created for interaction debugging, prompt
diagnostics, and primitive-navigation experiments; it was put away because our
main goal uses AsgardBench's existing action interface and evaluation rules.
Its restricted actions and different execution rules made comparisons confusing.
Read the decision and resumption guidance there before explicitly reusing it.

## Evidence and project history

- [progress.md](progress.md): dated experiments, failures, fixes, and decisions.
- [Official Qwen sanity report](reports/official_sanity_qwen_2026-11-12.md):
  completed 2/2 baseline after correcting context allocation.
- [Historical custom evaluation](reports/goal_generalization_2026-11-12.md):
  separate 17/19 result; not an official benchmark score.

The interactive replay is a separate viewer of recorded evidence, located at
`/data/5pourghe/sites/household-agent-replay/`. It neither runs nor chooses an
agent. Existing reports, evidence bundles, and replay assets remain preserved.
Generated results and screenshots are ignored by Git. No model training is
performed by this repository.

## Credits

[AsgardBench](https://github.com/microsoft/AsgardBench) supplies the benchmark;
[AI2-THOR](https://ai2thor.allenai.org/) supplies the simulator;
[Ollama](https://ollama.com/) serves the local VLM. LLaVA was used in the initial
experiments; the latest recorded baseline uses Qwen.
