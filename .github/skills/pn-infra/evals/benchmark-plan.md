# Copilot pilot

Status: planned, not executed. Use one low-complexity and one medium-complexity IaC task supplied by the user.

Compare five variants: Copilot baseline; pn-infra-ai-toolkit; AI-DLC; AI-DLC with SEND references; Spec Kit with the same SEND references.

Keep model, prompt, source revisions, available repositories and execution permissions equal. Start each run with fresh conversation and task state. Exclude old SEND Expert/Infra skills and prior solutions from discovery. Record the actual enabled instructions and tools; a different discovery set invalidates a clean comparison.

Use isolated source copies in an agreed evaluation workspace outside the distributable toolkit. Original SEND repositories remain read-only. Keep persistent evaluation artifacts in the agreed workspace. Framework-managed variants retain their own state instead of a second toolkit knowledge base and documentation folder.

Measure acceptance correctness, compatibility regressions, unsupported review findings, human interventions, active time, review waiting time separately, and tokens when observable. Do not claim token savings from elapsed time. The endpoint is approved review when available; otherwise explicitly report ready-for-review only.

Include a session-resumption exercise: a fresh conversation must recover next actions and verify source state using the artifacts, without the previous chat. Two task examples are exploratory evidence, not a statistically robust ranking.
