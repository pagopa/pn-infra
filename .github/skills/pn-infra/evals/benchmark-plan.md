# Evaluation protocol

Compare a baseline without the skill with the toolkit-enabled configuration. Additional framework variants may be included if their enabled rules and workflow differences are recorded explicitly.

Keep the model, prompt, source revisions, available repositories and execution permissions equal. Start each run with a fresh conversation and task state. Exclude unrelated skills and prior solutions from discovery. Record the enabled instructions and tools; differences in discovery must be reported when interpreting the comparison.

Use isolated source copies in an agreed evaluation workspace outside the distributable toolkit. Keep original repositories unchanged. Framework-managed variants retain their own workflow and task artifacts.

Measure acceptance correctness, compatibility regressions, unsupported review findings, human interventions, active time, review waiting time separately, and tokens when observable. Do not infer token savings from elapsed time. Report approved review only when approval occurred; otherwise report ready for review.

Include a session-resumption exercise: a fresh conversation must recover the next actions and verify source state using the recorded artifacts, without the previous chat. Small samples provide exploratory evidence, not a statistically robust ranking.

Record actual inputs, outputs and assessment results for every executed case. The presence of evaluation files does not establish that the cases have been run or passed.
