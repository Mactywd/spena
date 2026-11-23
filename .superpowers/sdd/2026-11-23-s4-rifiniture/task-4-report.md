# Task 4 report: i pesi seguono l'unità canonica

Done: `realign_weights` / `Realigned` in `services/unit_grams.py` (move, merge with hand-weight-wins and tie to the canonical row, drop for mass/volume, piece to NULL); `decide_grams` calls it first (`GramsRun.realigned`); `decide_unit_forms` calls it with the applied unit ids; `decide_units --imposta` calls it for that unit; the `decide_grams` command prints the realigned line; module and model docstrings updated.

TDD: RED = tests written, new source reverted, pytest on the task files -> ImportError: cannot import name 'realign_weights' (expected: function missing). GREEN = the 7 task files: 80 passed. Full suite via `suite`: 2421 passed.

Self-review: flush before each target lookup so merges see earlier changes in the same pass; no commit inside; unit_ids=None checks all rows. No migration.
Concerns: none.
