# Synthetic repository snapshots

Each Markdown file bundles one complete fixture workspace. Level-two headings give relative file paths; fenced blocks contain their contents. Five scenarios have two variants each. Use one variant per fresh session.

The cases and input paths are listed in [fixture-evals.json](../fixture-evals.json), relative to the evals directory. For a reasoning-only review, supply the selected snapshot as the repository evidence. To evaluate filesystem search or task-memory discovery, first reconstruct its listed files in an isolated test workspace, preserving the paths and contents. Then provide the task prompt and that workspace. A snapshot-only run does not test filesystem discovery.

Do not provide the paired variant or evaluator expectations to the candidate agent. File and line citations refer to the virtual files in the snapshot, or the reconstructed files when staged.

These are synthetic, read-only cases, not deployment packages. Do not execute the embedded scripts or perform AWS operations. They are public regression inputs shipped with the skill; use unseen cases with separate expectations for an unbiased benchmark.
