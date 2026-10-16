# Source and adaptations

The method is [OpenSkill: Open-World Self-Evolution for LLM Agents, v1](https://arxiv.org/abs/2606.06741v1), especially §2.1–2.2, Appendix A.5 and Appendix B. The inspected implementation is [OpenLAIR/OpenSkill at 84ca182](https://github.com/OpenLAIR/OpenSkill/tree/84ca182da055fafb6453dcec4a6defdbbfd987c1).

| Method component | Source at that revision | Penguin implementation |
| --- | --- | --- |
| Research query, domain knowledge and 1–4-skill plan | `libs/openskill/agent_planner.py`, `pipeline.py`, `skill_planner.py` | Two research passes and a fixed per-Case plan in the main Skill |
| Verification knowledge distinct from background research | `pipeline.py::_run_surrogate_dr` | Independently sourced anchors in `verification-knowledge.md` |
| Persistent creator, independent verifier, no GT oracle | `openskill_evolution.py::OpenSkillAgentBase._check_episode_exit`, `libs/terminus_agent/evolution/independent_verifier.py` | A persistent SDK creator; fresh verifier Agents in separate containers; controller-mediated feedback |
| Failure diagnosis and targeted retrieval | `libs/openskill/targeted_dr.py` | `SELF-FIXABLE` / `NEEDS-DR`, up to three searches per Case |
| Final skill export | `openskill_evolution.py::_export_skills_to_logs`, paper B.6 | Freeze the last revision, not the highest virtual score |
| Zero-shot final evaluation | `pipeline.py::_run_evaluation`, paper §2.2.3 | The unchanged shared `evaluation.md`, invoked only after the global freeze |

The paper's Appendix F includes a sentence about a GT pass/fail bit when expanding verifier tests. That conflicts with §2's supervision-free definition and Appendix B's final-only evaluation. The OpenSkill override in the inspected code exits at a surrogate pass before the inherited GT oracle. This port follows that override and §2: **no GT signal, including one bit, enters construction**.

The source's retry cap is checked before the next verification. A third failure can trigger a final edit which is exported without testing again. The port preserves this ordering and records which revision the last virtual result actually describes. The paper's short description of “three rounds” should not be interpreted as three verified revisions plus a separately tested seed.

Declare the following adaptations when used:

- Penguin's configured model and research tools replace the paper's particular Gemini research/classifier endpoints and Terminus creator. Record actual model identities and sampling defaults; do not claim those proprietary endpoints were used.
- New `isolated-v1` runs use separate Docker containers for each author and measurement, with the SDK model transport outside them. Earlier execution modes retain their recorded behavior. The reviewed image must reproduce the public task environment without graders or solutions.
- Learned skills live under one Target-owned wrapper so native State loading, snapshots and evaluation work without host changes. For multiple Cases, all task skills coexist in one frozen library and route by public applicability; upstream deploys a separate set per task. The wrapper is fixed plumbing, not a learned fifth skill.
- A fresh Target matches the no-initial-skills setting. Reusing a Target with domain skills is a warm start and must be reported separately.
- A baseline comparison is optional and happens after the global freeze. The smoke profile uses one final run per Case; the paper uses five. A generic workspace Rubric gives a `0..100` benchmark score; a Harbor verifier supplies reward × 100. Neither is the virtual test pass rate.
- The virtual parser reads pytest's JUnit report, counts executable tests excluding skips, and refuses invalid reports rather than estimating a proxy score. Missing-output assertions are ordinary task failures; verifier infrastructure errors remain unscored. Required-check coverage is an additional pass gate.
- The port caps issued targeted searches, including unsuccessful requests; upstream increments its counter only when research text is returned. Context/episode guards are replaced by explicit, observable budgets where Penguin lacks the source's counters, with a 30-minute construction limit per Case in the smoke profile.
- Queries also remove task identifiers and solution-locating URLs. The inspected pipeline's literal keyword filter covers SkillsBench spellings; the stronger filtering here implements the paper's broader information-isolation requirement across arbitrary Benchmarks.

OpenSkill's virtual verifier is imperfect. The paper reports both false positives and false negatives, including format-only checks and verifier infrastructure failures. Report proxy results and final target results separately. A high virtual pass rate is neither proof of improvement nor a reason to relax the final Benchmark.

## Protocol review for the 2026.10.15.1 Skill

The implementation was checked against v1 §2.1–2.2, A.5, B.1–B.6 and F. The supplied
`2606.06741v1.pdf` was truncated at 11,010,048 bytes, without a PDF trailer. The complete
[arXiv v1 PDF](https://arxiv.org/pdf/2606.06741v1) was downloaded separately; its first
11,010,048 bytes exactly match that local file. The original file was not changed.

| Property | Paper location | Implementation after this change |
| --- | --- | --- |
| Fixed model weights; learn reusable skills | §2.1 | The learned artifact remains the Target's skill library |
| No target supervision during construction | §2.1–2.2, B.3 | No scored worker before global freeze; the helper neither reads Benchmarks nor invokes graders |
| Domain research plus independent verification anchors | §2.2.1, B.1–B.2 | Both retrieval passes and query filtering remain required |
| Fixed plan of 1–4 skills; persistent creator | §2.2.2, B.1, B.4 | The journal fixes the plan/creator and records all revisions |
| Separate verifier; deterministic tests | §2.2.2, B.3 | Fresh verifier context, JUnit parser, at most 60 tests; creator implementation remains excluded |
| Gap versus bug classification | B.5 | `SELF-FIXABLE` default and `NEEDS-DR` retrieval remain; issued searches consume the declared budget |
| Last revision, not best-of-N | §2.2.3, B.6 | No score-based selection or rollback; final and last-tested hashes are separate |
| Freeze before independent target execution | §2.2.3, B.6 | Frozen library and exact Case × runs plan precede baseline/control/final measurements |

These additions are engineering adaptations: stable artifact ids and portable contracts;
append-only execution records; an explicit public-requirement coverage map; usage self-reports
with separate trace audits; and validation of the declared matrix. They do not constitute an
OS-enforced sandbox or a semantic proof of verifier quality. Each issued pytest attempt,
including a verifier repair, spends the existing Penguin retry budget. This accounting is
stricter than treating multiple internal verifier repairs as one host invocation; disclose it
when comparing compute budgets with the paper.

Two optional experimental adaptations are disabled unless requested: a held-out Benchmark
separates construction tasks from evaluation tasks, and an empty-reader control measures the
deployment mechanism separately from learned content. Neither is the paper's default per-task
experiment, neither selects artifacts, and all measurements remain after freezing. Without
these options the original same-task baseline/final protocol is preserved. The paper's five
final runs, model endpoints and episode counters are still not claimed by the smoke profile.

The Appendix F pass/fail-bit ambiguity described above remains unresolved in the text.
This implementation continues to admit no GT bit into construction, consistent with §2 and
the inspected OpenSkill override. No new optimization changes that interpretation.

## Feedback repair in the 2026.10.16.1 Skill

Rechecked [v1 §2.2 and B.3–B.6](https://arxiv.org/html/2606.06741v1) and the pinned
`openskill_evolution.py::_check_episode_exit`. Failure diagnostics still guide the same
creator; hidden supervision remains unavailable until freeze. The final failed attempt may
produce an unverified last revision, with no best-of-N selection or extra verification.

Schema-2 journals add execution receipts, mandatory recovery decisions, retrieval-result
evidence, explicit verifier execution status and evidenced early stops. Unchanged practice
reruns and verifier repairs are counted separately from skill changes. These are Penguin
execution safeguards, not additional learning stages or paper hyperparameters. Requiring
retrieved evidence before acting on `NEEDS-DR` is stricter than upstream's fallback after
empty research; an unresolved gap remains explicit. Existing retry/search caps stay unchanged.

Deadline guidance is read-only; the controller still stops processes and checks tool traces.
Hashes establish byte identity, not causal improvement or correct verifier semantics.
Existing experiments retain their recorded Skill version; this version does not reinterpret
their results. The local executable regression checks the feedback-to-revision path, not
Benchmark performance.

## Isolated execution in the 2026.10.16.2 Skill

Rechecked [v1 §2.2, A.5, B.3–B.6 and F](https://arxiv.org/html/2606.06741v1).
The executor preserves the fixed model, 1–4-skill plan, persistent creator, independent
verifier, failure-driven feedback, retrieval budgets, last-revision export and global
freeze before target scoring. It does not add candidate selection or a GT feedback channel.

The engineering changes are a host-owned SDK launcher, distinct container filesystems,
allowlisted input/result transfer, actual process receipts, cancellation and recovery.
The default practice mode keeps model-driven skill application, including Markdown skills;
explicit command practice is a declared adaptation for executable tasks. Authoring and
practice use separate clean containers and read-only practice skills. The controller still
performs research and diagnosis with Penguin's configured tools and model, not the source's
Gemini endpoint. Hosts must export state-only task outcomes to explicit public artifacts.

Isolation is conditional on a reviewed image and clean controller-supplied content. It
prevents direct cross-role file access; it does not prove that retrieval is uncontaminated,
that a skill was meaningfully applied or that a verifier is correct. Local SDK/Docker tests
exercise process isolation and a failed-test → same-creator repair → passing-test loop.
These tests make no claim about benchmark gains. Previous runs and the shared final
evaluation protocol remain unchanged.
