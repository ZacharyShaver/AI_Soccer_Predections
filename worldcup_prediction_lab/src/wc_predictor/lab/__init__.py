"""Daily model-research lab: variant registry, experiment runner, leaderboard.

Claude orchestrates Codex to build new feature-model variants (one per git
worktree) each day; each variant's predictions are scored against the next
day's actual results and ranked on a running leaderboard. Every challenger
must beat the plain Elo baseline (the bar).
"""
