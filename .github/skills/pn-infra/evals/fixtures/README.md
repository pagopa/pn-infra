# Fixture inputs

Each Markdown file contains one fixture workspace. Level-two headings identify relative file paths; fenced blocks contain file contents. Five scenarios have two variants each. Use one variant per fresh session.

Prompts, input paths and assessment criteria are listed in [fixture-evals.json](../fixture-evals.json). Paths are relative to the evals directory.

For a reasoning-only review, provide the selected snapshot as repository evidence. To evaluate filesystem search or task-memory discovery, reconstruct its files in an isolated workspace, preserving paths and contents. Then provide the task prompt and workspace. A snapshot-only run does not test filesystem discovery.

Do not include the paired variant or expected answers. File and line citations refer to the virtual files in the snapshot or to the reconstructed files.

These are synthetic, read-only inputs. Do not execute embedded scripts, deploy resources or perform AWS operations.
