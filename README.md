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
- LLaVA 7B processed a simulator image through Ollama.
- The first two-task AsgardBench sanity check had **0/2 successes**.
- The responses described scenes but contained no usable actions.
- The cause remains under investigation.

There is currently no claim of successful autonomous task completion or model
training.

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

## Limitations

The initial sanity-check responses were descriptive rather than executable,
and both tasks failed. The reason is not yet established. Results should not
be interpreted as evidence of autonomous completion or training.
