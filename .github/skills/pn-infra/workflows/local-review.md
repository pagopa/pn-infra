# Local review procedure

1. Establish the diff and intended behavior. Inspect changed files and necessary callers, consumers and deployment scripts.
2. Select applicable sections of `references/iac-guidelines.md` and `references/architecture.md`, relative to the skill root; read them before applying their checks.
3. Follow cross-stack parameter contracts, permissions and lifecycle implications where touched. Distinguish an established defect from a decision that requires clarification.
4. Report actionable findings with file and line, triggering scenario, consequence and supporting evidence. Cite the relevant SEND rule when it explains a non-obvious requirement.
5. Avoid generic AWS advice, unrelated pre-existing problems and preferences not supported by a rule or concrete impact. Do not report a missing resource or configuration merely because its source is in another repository.
6. State unavailable cross-repository evidence and unexecuted checks. If no supported findings remain, say so without claiming deployment correctness.

This procedure applies to a local diff, working tree or files already available in the workspace. Preserve source code, Git state and remote systems. Only agreed local review documentation may be written; a request for fixes selects development. Report unresolved material assumptions in the review result.

Use this finding shape: `file:line — defect; triggering condition; impact; evidence`. Separate confirmed findings from verification gaps. Do not pad the report with a mandatory minimum number of findings, and do not approve a PR on behalf of the user.

## Persist the review

Follow [local review memory](../references/task-memory.md#local-review-memory): offer `local-review/REVIEW.md` in the matching task memory, or propose a new memory when none matches. Respect an explicit request to save or remain in chat; otherwise obtain agreement before writing. Use the [report sections](../templates/task-documentation.md#local-review-report), record supported findings and limitations, and preserve source code and Git state. Recheck current sources when resuming a saved review.
