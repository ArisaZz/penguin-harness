# Verifier evidence regression

This small authored fixture reproduces the failure pattern observed in the
2026-10-16 and 2026-10-19 GDPevo development runs: permissions and diagnostic
thresholds were not established by the cited public data. The latter verifier
labelled those requirements covered anyway. It contains no benchmark answers,
grader code, held-out tasks or creator implementation.

`plan.json` deliberately includes two unsupported claims with real but irrelevant
quotations. `review-decisions.json` is a human-readable controller assessment of
these fixed claims. The validator checks source membership and enforces the review;
it does not discover semantic entailment automatically. A positive result requires
the arithmetic check to remain usable and both unsupported requirements to remain
unverified. Deleting either requirement is also a regression.

Use `public/`, `research/` and `outputs/` as explicit file maps with
`scripts/verifier_replay.py` to test a real construction model independently of
skill generation. Do not give the model the fixture plan or review decisions during
its planning stage. Inspect its own plan before preparing a matching review.
Replay results are development evidence, never GDPevo scores or deployable skills.
