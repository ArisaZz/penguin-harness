# Method and provenance

This plugin carries the Evo learning adaptation frozen at `.6`, commit
`1b56cb777e515564fd6b2059818ae165242bb560`. Its implementation reference is
[A-EVO-Lab/a-evolve at 3c7c7b8](https://github.com/A-EVO-Lab/a-evolve/tree/3c7c7b8c62a3f07da1d4407aa03f0ca079954bcf),
in particular the CL path in `evo_harness/cl_bench.py`. The underlying paper is
[Evo-Harness, arXiv 2608.15071v2](https://arxiv.org/abs/2608.15071v2).

The CL proposal path retains the Solver's messages and model, appending negative
feedback to that same context. Here a native Solver continues through the real
grade and reflection; `input_subagent` can deliver feedback to that same Session.
One independent Evolver then curates all negative candidates against the full
training batch and pre-batch library with ADD/MERGE/REVISE/SKIP. No fresh
Reflector reconstructs history, and no candidate evaluation or score gate is
introduced. Successes supply counterevidence, not positive-source candidates.

The pinned CL `_build_system_prompt` loads all current-context bodies and general
descriptions. This adaptation retains that distinction, with independent native
Skill directories and a fixed Reader. The private library retains general bodies;
the exported general files expose descriptions only. Five general entries, five
per topic and a 16,000-byte complete package are ceilings, not quotas. This byte
budget is an adaptation, not an exact token budget or a published-score claim.

GDPevo training uses its documented continuous environment and feedback route.
Each task is answered and scored once before one batch compilation. Frozen Base
and learned States then transfer to fresh held-out trials, three complete Test
repetitions by default. There is one learning run and no cross-training-run
variance or iterative optimization curve. Other Benchmarks use their own native
tasks, splits and grading but must provide original-session training feedback.

The native plugin uses existing delegation, Session continuation and State
interfaces. Prompt-file transport, scoped guard hooks, private runtime patches,
historical replay and acceptance tooling are not part of this package. The
helper validates data and rendering; method adherence requires native trace
inspection. Earlier experiment artifacts and verdicts keep their original format
and identity; this workflow neither migrates nor relabels them.
