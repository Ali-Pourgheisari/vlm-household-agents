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

## Current progress

- AI2-THOR rendered screenshots and executed a rotation.
- A scripted pickup succeeded on November 5, 2026: a credit card was picked up
  in FloorPlan1, confirmed by object metadata and inventory.
- LLaVA 7B processed a simulator image through Ollama.
- The first two-task AsgardBench sanity check had **0/2 successes**.
- A custom prompt workaround produced `Action: OPEN Fridge`, accepted by the
  unchanged benchmark parser. That model-generated action was not executed.

The [investigation report](reports/ollama_llava_action_diagnostic_2026-11-01.md)
records the diagnostic findings. The next step is to use actual simulator
object identifiers, execute model-selected actions, and rerun the sanity check.
Autonomous task completion and model training have not been demonstrated.

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

## Investigation and limitations

The initial sanity-check responses described scenes without usable actions.
Follow-up experiments identified request compatibility, context handling,
output limits, and object-vocabulary adherence as separate issues. A compact
output contract with explicit native context/output settings produced one
parser-accepted action; it has not been integrated into the benchmark.

See the [investigation report](reports/ollama_llava_action_diagnostic_2026-11-01.md)
for results and evidence limitations. The one-off diagnostic scripts were
removed because they depended on local, ignored experiment artifacts. The
three retained scripts check rendering/movement, image inference, and scripted
pickup; none runs an autonomous model-controlled task loop or trains a model.

Generated screenshots and results remain local and ignored by Git.
