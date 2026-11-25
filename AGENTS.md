# Project working instructions

## Progress log

- Read `progress.md` before starting project work.
- Update `progress.md` whenever you perform project work, including code or
  documentation changes, experiments, investigations, debugging, and publication.
- Use dated entries in Europe/Berlin time. Record the work, bugs/problems,
  observed evidence, attempted fixes (including failed attempts), actual outcome,
  validation, remaining issues, and relevant report/artifact paths.
- Preserve earlier entries. Distinguish verified results from hypotheses and
  proposed work; do not describe recommendations as implemented changes.
- Record important failures as well as successes, and distinguish first-attempt
  success from success after changing settings or retrying.
- Link detailed reports rather than duplicating them in full. Generated results
  remain ignored; never include secrets or base64 image payloads in the log.
- Keep README.md focused on project purpose, setup, usage, and scope. Put progress
  history and experiment results in `progress.md` and link to it from the README.

## Main runner and parked experiments

- Use the official AsgardBench runner for normal evaluations. The supported
  entry point is `python3 scripts/run_benchmark.py`, which delegates to the
  external `AsgardBench.Model.model_tester` without a custom action loop.
- The custom runner is parked in `experimental/custom_runner/`. Do not resume,
  expand, or silently fall back to it unless the user explicitly requests it.
  Read its README for why it exists, why it was put away, and resumption guidance.
- Keep official benchmark and historical custom-runner results separately
  labeled; their action abstractions, rules, setups, and goal checks differ.
- Preserve historical reports, raw results, source snapshots, and replay assets.
