# Custom runner — parked

Status: inactive for normal project work as of November 12, 2026.
The main runner is [AsgardBench](../../README.md). Nothing here is selected or
called by the official launcher.

## Why it exists

This code grew from narrow debugging experiments: sending screenshots to a VLM,
parsing its choices, validating object interactions, recording failures, comparing
prompts/schema constraints, and testing model-selected primitive navigation.
It uses AI2-THOR directly, reusing some AsgardBench parsing/prompt components.
It was not a complete AsgardBench integration.

## Why it was put away

The user chose AsgardBench as the main runner on November 12, 2026. Our intended
workflow is evaluating VLM household agents using the benchmark's existing tasks,
actions, execution rules, and goal evaluator. Expanding a separate runner
duplicated functionality and introduced a smaller action vocabulary, different
execution assistance/rules, and results that cannot be directly compared.
For example, this runner lacks PUT; AsgardBench already supports it. Direct TV
toggling also bypasses the benchmark's held-remote requirement.

This is a workflow decision, not evidence that the code is unusable or that
AsgardBench solves every navigation problem. Primitive-navigation and prompt
diagnostics may still be useful as separately defined research experiments.

## What is preserved

- `household_agents/`: custom model interface, executor, task checks, and recovery.
- `scripts/`: original custom episodes, interaction demos, and diagnostics.
- `tests/`: existing offline regression tests.
- [USAGE.md](USAGE.md): previous detailed usage guide, with relocated commands.
- Historical reports remain in [reports/](../../reports/), and raw evidence stays
  in repository-root `results/`. Git history preserves original source paths;
  saved source snapshots and the separate replay viewer remain unchanged.

The official 2/2 sanity result used AsgardBench. The custom 17/19 result used
this separate runner with mixed starting protocols. Neither is a general
reliability estimate; do not merge their scores.

## When to use it again

Resume only when the user explicitly requests custom-runner work or approves a
research question requiring it. State the different action abstraction, setup,
rules, and scoring before comparing results with AsgardBench. Do not silently
fall back here when an official benchmark run fails.

From the repository root, the preserved tests can be run without model calls
or simulator execution:

```bash
cd experimental/custom_runner
uv run --project /data/5pourghe/AsgardBench --no-sync \
  python -B -m unittest discover -s tests -v
```

Custom scripts retain their names under this directory. Run them from here
following USAGE.md. Their new generated outputs live here under ignored
`results/` or `environment_test/`; old outputs were not moved. The parser
dependency defaults to the sibling AsgardBench checkout and can be overridden
with `ASGARDBENCH_DIR`.
