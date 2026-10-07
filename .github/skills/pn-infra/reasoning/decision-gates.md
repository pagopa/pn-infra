# Material decision gates

Match the gate to the change, not to a fixed lifecycle.

| Situation | Required decision |
| --- | --- |
| Clear local change within approved scope | Proceed with proportionate verification; no additional ceremony. |
| Unresolved domain, cross-account access, rollout or functional purpose | Resolve the material choice before implementing the dependent design. |
| Stream starting position, replay, persistent-data replacement or deletion | Explain continuity and data impact; obtain explicit authorization for the proposed change. |
| pn-configuration edits, deployment or AWS mutations | Obtain explicit authorization for that operation; an approved local implementation plan does not grant it. |
| Local branch creation/selection | Follow the approved per-repository branch/base strategy and protect working-tree changes first. |
| Commit or integration; push/pull/fetch | Keep commit, merge, rebase and cherry-pick manual; remote Git synchronization is outside these workflows. Stop for required user integration. |
| PR documentation | Reuse matching memory; ask before creating a new review folder. Only agreed documentation may be written, not source or remote state. |
| New cross-repository scope beyond the request | Explain the dependency and obtain agreement on the expansion. |
| Missing source evidence or failed check | State the gap or failure. Do not mark the affected criterion verified. |

Reuse an approval only for the same scope and operation. Record consequential decisions with their rationale and evidence, not conversation transcripts. When a framework already owns the plan and approval record, use it instead of creating a parallel gate system.
