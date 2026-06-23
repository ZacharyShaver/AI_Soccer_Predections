"""Model-variant package.

Each module here is ONE candidate model and must expose:
  - VARIANT_ID: str         unique id (also the prediction model_id / ledger filename)
  - DESCRIPTION: str        one line
  - FEATURE_IDEA: str       the data/feature hypothesis being tested
  - build_model(*, generated_at_utc: str) -> model with fit/predict_match/predict_scoreline

Adding a variant = adding a file. The registry auto-discovers modules, so
variants built in parallel git worktrees never touch a shared file and never
merge-conflict.
"""
