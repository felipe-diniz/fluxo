<One sentence on what the session delivers.> Owner's request on <date>, in their words: "<literal text>". <If there was a choice: "Owner's decision (<date>, among N options): <label>. In the chosen option: <option text>." Do not reopen the decision.> <If there was an approval: Approved by the owner (<date>): "<literal text>", valid for <what, where>. Outside that, nothing is approved.> On branch `<branch>` of checkout `<checkout>`, no new branch, autonomous session.

Decisions already made (asked of the owner before launch, <date>, literal): <doubt → answer, and where it applies>. A doubt this list answers does not go back to the coordinator: follow the answer.

The contract and what exists (check before writing):
- the contract: <PRD, front plan or ADR, with this phase's sections>; read the sections whole;
- <the measured fact: baseline, log without PII, reproduction; production read-only and count>;
- <the code map: files, functions, invariants already checked by the coordinator>.

Scope (decide the details with the skills and record the why in the contract):
1) <item>;
2) <item>;
Stays OUT: <what is not included and why: the next phase, another front, refactoring what was not asked>.

Invariants (non-negotiable): <those from the project's critical-risk doc that this front touches, and the owner's hard rule that applies>.

Before writing: the skills <of the layer the front touches> via the Skill tool, only with the references of the topic; the project's critical-risk doc and only the reference of the touched domain <which>; the memories <of the domain>.

Proof: level <P | M | C> (skill coordinate-sessions, §7): <the why, in one line>. Tests (the project's test skill, if any): the test first and the red seen; <cases: CAS with count 0 and 1, other tenant blocked, timezone near midnight, hostile argument, no-op retry…>.

Delivery gate (what you hand back measured, never asserted): <1) suites touched with the count; 2) the profile's typecheck/lint; 3) screen, if there is UI>.

Docs: <the contract with the "Done on <date>" and the pending items; the layer's skill if the rule changed; the risk reference if an invariant changed; i18n in the project's languages> in the delivery commit or in a `docs(...)` right behind it; memory in its own commit.

Closing: delivery gate green; ONE `keel:critical-review` gate at the end, only if critical risk was touched, over the critical hunks and their siblings; fix what comes back; <commit per the footer rules | do NOT commit: the owner has not authorized yet>; final report to the coordinator.
