# OpenSkill 在 PenguinHarness 中的集成问题与验收建议

- 初次记录：2026 年 10 月 13 日；本次更新：2026 年 10 月 14 日。
- 适用版本：PenguinHarness `0.2.13`，基础提交 `64aebf0f`。
- 核查对象：`feat/openskill-rsi-toolkit` 分支工作区中的新增插件，Skill 版本 `2026.10.13.1`。
- 工作目录：`/home/qx/penguin-harness-wt/openskill-rsi-toolkit`。
- 本次评估会话：[`session-2026-10-14-03-34-26-e6971672`](http://localhost:7365/chat/session-2026-10-14-03-34-26-e6971672)。时间均按 UTC 记录。
- 审计材料：Controller 主会话、51 个直接子会话、20 次 Harbor 正式评测的 Target trace，以及技能、虚拟测试、冻结清单和原始评分文件。

## 一 会议结论

OpenSkill 已完成插件内容编写、局部测试、本地页面展示验证及首轮真实模型实验。2026 年 10 月 14 日，Sec-A 的 10 个 Case 分别完成基线和技能版本各一次正式评测，评估中心得分由 70 提升至 80。20 个评分结果与 Harbor 原始记录一致；Target 最终保留冻结的 v2 状态。

Trace 审计确认流程能够运行，也发现八类运行问题：技能读取不完整、字段语义与评分契约歧义、虚拟验证覆盖缺口、部署路径不兼容、执行超时未披露、重试预算与记录不一致、构建期访问边界未严格落实，以及实验记录和用量报告不完整。八类问题对应 OS-02、OS-07 至 OS-13；原有分发及发布检查缺口继续保留。单次得分提升尚不足以证明稳定增益或论文同配置复现。

评估中心的中英文提示词冲突已于 10 月 13 日修复。本次 trace 确认正式评测发生在全部技能冻结之后，没有对中间候选进行正式评分；但空记分板读取、技能使用及重试计数等执行偏差说明，入口指令修复并不等于全部协议已得到强制保障。

初始实现将代码改动限制在 `plugins/` 内；随后获准修改 Web 提示词，并补充了对应回归测试及双语变更记录。宿主依赖声明、官网目录和项目文档尚未同步，其他问题的修复范围仍待决策。

## 二 当前集成方式与完成范围

OpenSkill 通过 `openskill-rsi-toolkit` Skill 接入 PenguinHarness。控制 Agent 按 Skill 指令组织知识检索、技能创建、独立验证和最终评估；新增 Python 脚本负责解析虚拟测试结果。主要算法流程由 Agent 执行，尚未实现为独立的、由程序强制控制阶段转换的算法引擎。

当前约定的执行顺序为：

```text
准备公开任务输入并保存未评分的基线
                 ↓
检索领域知识及独立验证依据
                 ↓
创建技能 → 执行练习任务 → 独立虚拟测试 → 按失败原因修订
                 ↓
所有任务结束后冻结最后版本的技能
                 ↓
在相同运行配置下评估基线与最终版本
                 ↓
将正式评估结果写入评估中心 scoreboard.yaml
```

这里的“虚拟测试”是依据公开任务要求和独立资料生成的检查；“正式评估”使用 Benchmark 的评分机制。两者的结果必须分别记录，虚拟通过率不能替代正式得分。

| 层面 | 当前状态 | 能够支持的结论 |
| --- | --- | --- |
| 插件内容 | 已包含清单、图标、主 Skill、初始化与评估参考、Python 解析器和单元测试 | 插件结构和执行协议已形成 |
| 本地加载与页面 | 此前在该 worktree 的开发实例中，通过本地安装加载并查看过插件卡片及详情 | 插件能够进入服务器插件库并显示 |
| Agent 使用 | `openskill_controller` 已运行该 Skill，`openskill_target` 已接受基线及技能版本评测 | 集成已实际执行；技能读取覆盖仍不完整，见 OS-07 |
| 自动化检查 | 10 月 13 日局部检查通过，但文档及官网同步检查存在失败 | 这是历史检查结果，本次文档更新未重新执行这些测试 |
| 算法效果 | 首轮 10 个 Case 的正式分数为 70 → 80，每版本每 Case 运行一次 | 可报告本次差值及正式评测成本，尚不能证明稳定增益 |

页面展示是此前验证结果，不代表当前服务仍在线。服务器安装、Agent 安装和算法实验完成是三个不同的验收层次。

## 三 问题清单

优先级按处理门槛划分：P1 表示在宣称协议合规或稳定算法收益前处理或验证；P2 表示在扩大实验或发布前完成。性质列区分已观察问题、待澄清契约和历史验收缺口，不能将风险项直接写成已发生的数据泄漏。

| 编号 | 问题 | 性质 | 主要影响 | 优先级 |
| --- | --- | --- | --- | --- |
| OS-01 | 评估中心通用指令与 OpenSkill 评估时机矛盾 | 已修复提示词 | 真实执行仍纳入 OS-03 验收 | 已处理 |
| OS-02 | 构建期评分隔离边界未严格落实 | 已观察访问偏差；未确认目标监督泄漏 | 有历史评分时可能污染构建上下文 | P1 |
| OS-03 | 首轮实验已完成，稳定性与完整协议尚未验收 | 部分完成 | 单次差值不能证明稳定增益 | P1 |
| OS-04 | 未加入宿主的内置插件依赖 | 已确认 | 本地可见不能保证新安装或发布包默认携带 | P2 |
| OS-05 | 文档与官网同步检查失败，Python 测试未接入默认测试入口 | 已确认 | 当前发布检查不完整，持续回归保障不足 | P2 |
| OS-06 | 多任务部署、环境和预算与论文配置存在适配差异 | 已声明差异及待验证风险 | 实验结果不能直接视为论文同配置复现 | P2 |
| OS-07 | 只有 5 个 Case 读取了对应技能 | 已确认 | 效果归因混合了使用和未使用技能的执行 | P1 |
| OS-08 | Case 004 的字段解释与评分要求不一致 | 已确认；公开契约有歧义 | 虚拟测试通过但正式关键字段失败 | P1 |
| OS-09 | 已识别的关键验证缺口未阻止成功终止 | 已确认 | 100% 虚拟通过率夸大需求覆盖程度 | P1 |
| OS-10 | 32 个技能保留练习环境固定路径 | 已确认 | 正式执行依赖 Agent 临场定位和改路径 | P2 |
| OS-11 | 完成产物后持续检查直至超时，报告遗漏运行异常 | 已确认 | 额外耗时且成功评分掩盖执行超时 | P2 |
| OS-12 | 验证尝试、修复与重试预算记录不一致 | 已确认 | 难以复现实际计算预算及验证历史 | P1 |
| OS-13 | 实验记录解析失败未修复，用量信息未完整汇总 | 已确认 | 自动汇总、成本比较和审计不完整 | P2 |

### OS-01 评估中心指令冲突已修复

**修复前的原因。** 评估中心的中文 `rsiOptimizeTail` 对所有非默认 RSI 方法使用“基线与每个候选都经技能自带的评测参考测量”，英文也要求测量 baseline and every candidate。OpenSkill Skill 则明确禁止在构建阶段查看目标分数，并要求先完成全部任务的技能冻结。

**通俗解释。** OpenSkill 的做法类似“先查资料、做自拟练习，教材定稿后再参加正式考试”。原通用指令会要求每个教材版本都接受正式考试；若这些成绩用于继续修改教材，就改变了验证方法。

**原有影响。** Skill 要求遇到冲突请求先澄清，因此原入口可能导致点击优化后不能直接开始。若执行 Agent 忽略冲突、边看正式分数边修订，则结果不能标为当前协议下的 OpenSkill 实验。此次修复依据是指令矛盾，没有证据表明已经发生了一次违规优化。

**已实施修复。** 两种语言均按 `p.skill === "openskill-rsi-toolkit"` 使用专用指令，要求构建阶段仅使用独立虚拟反馈、禁止读取正式评分信息，全部 Case 的技能冻结后才评估基线与最终版本；禁止逐候选正式评分，以及根据正式结果继续修订技能。虚拟结果单独保存，只有完整正式评估进入 `scoreboard.yaml`。其他 RSI 方法保留原指令。

**验收边界。** 提示词回归检查覆盖中英文 OpenSkill 分支及 ACE、APE、AWM、OPRO 原有评估要求。该检查不能证明 Agent 在真实任务中一定遵守指令，实际执行记录仍按 OS-03 验收。

**已改动范围。** `packages/web/src/lib/strings.ts`、`strings-en.ts`、`packages/web/test/benchmark-prompts.test.ts`，以及双语变更记录和本报告。评分存储格式未变更。

证据：[中文指令](../../packages/web/src/lib/strings.ts)、[英文指令](../../packages/web/src/lib/strings-en.ts)中的 `rsiOptimizeTail`；[主 Skill](skills/openskill-rsi-toolkit/SKILL.md)中的 `Conflicting requests` 和 `Freeze, deploy and evaluate`。

### OS-02 构建期评分隔离边界未严格落实

**事实与原因。** 当前 Skill 规定了公开输入白名单、检索词清理、创建者与验证者分离、冻结后禁止修改等要求。多数检查由控制 Agent 执行；插件没有提供统一的程序化阶段门禁或独立的权限控制实现。初始化参考明确说明：新建会话只能隔离对话，不能自动隔离文件访问权限。

**本次观察。** Controller 在 03:34:32 读取了 `scoreboard.yaml`，03:35:06 尝试列出 `.jobs`，03:35:07 用 `wc -c` 读取各 `rubric/README.md` 的字节数。当前 Skill 禁止构建阶段打开这些评分路径，因此访问行为已经偏离协议。当时记分板为 `evaluations: []`；这些操作没有展示 rubric 规则文本，也未发现因此获得实际目标分数。不能据此认定本次发生了目标监督或答案泄漏。

**影响。** 在已有历史评分的环境中，相同的记分板读取行为可能将目标反馈带入构建上下文。新建子会话不足以阻止此类文件访问；未来实验仍需限制各角色的实际可见目录。

虚拟评分解析器能判断 JUnit 报告是否有效、如何计算通过率，但不能证明测试的期望值正确、覆盖了任务全部要求，或确实独立于创建者输出。形式检查全部通过，也可能伴随任务内容错误。

**建议与验收。** 构建角色只获得白名单输入，不暴露记分板、rubric、旧任务输出和评分 trace。保存检索词、资料来源、角色输入、测试及冻结哈希；用不含真实评分信息的隔离检查确认禁止路径无法访问。已接触本次正式评分反馈的会话不能继续用于宣称无目标监督的新一轮构建。

**改动范围。** 部分检查可在插件内补充脚本；若要统一约束宿主工具权限或阶段行为，需要进一步评估 core/server 改动，不能仅靠加强提示词宣称完成。

证据：[主 Controller trace 第一部分][trace-main-1]第 22、80、83 行；[初始化协议](skills/openskill-rsi-toolkit/references/initialization.md)中的 `Isolate construction inputs`；[虚拟评估协议](skills/openskill-rsi-toolkit/references/virtual-evaluation.md)中的 `Independent verifier`；[结果解析器](skills/openskill-rsi-toolkit/scripts/virtual-results.py)。

### OS-03 首轮实验已完成，稳定性与完整协议尚未验收

**事实。** 本次真实模型实验已完成“检索—创建—虚拟修订—冻结—部署—正式评估”。10 个 Case 共生成 40 个技能，最终虚拟测试为 426/426；基线通过 7 个 Case，技能版本通过 8 个。全部正式评测使用 `deepseek/deepseek-flash`、`thinking_level: medium`，每个版本每个 Case 运行一次。

**已验证与限制。** 本次证据支持角色调度、快照恢复、完整评分矩阵入账和保留最终 v2 状态能够运行；正式结果及模型成本有原始文件支撑。新增通过仅来自 Case 002 的数值输出精度修正。缺少重复运行、新任务泛化证据及完整构建成本，且 OS-02、OS-07 至 OS-13 尚未处理，因此不能认定全部协议验收通过或获得稳定能力提升。

**后续验收。** 先处理本次发现，再使用明确冻结的协议、干净的构建上下文和固定模型配置开展受控验证。重点确认：

1. 创建者使用虚拟反馈修订，构建阶段没有正式评分信息。
2. 冻结记录与实际部署的技能一致，Target 的执行记录能够证明其读取了适用技能。
3. 基线和最终评估使用相同运行配置；每个完整矩阵的 State 哈希保持一致。
4. 正式结果准确入账，结束时保留冻结的最终版本；失败和未完成评估没有被写成成功或零分。

复测同一个冻结技能库可以补充运行波动证据；如果根据本次评分修改技能，必须标明已使用评测反馈，不能将其作为同一无监督实验的延续。效果研究还需明确重复次数、任务集合和费用预算。

**改动范围。** 见各具体问题。本文只记录发现及验收建议，评分规则、运行状态协议和宿主权限控制的变更需分别确定范围。

证据：[正式记分板][scoreboard]、[基线矩阵][matrix-baseline]、[最终矩阵][matrix-final]、[冻结清单][freeze]及[最终状态清单][state-final]。

### OS-04 本地安装尚未等同于产品默认分发

**事实与原因。** core、CLI、desktop 的 `package.json` 均未声明 `@penguinharness/openskill-rsi-toolkit`。内置插件加载器根据宿主依赖查找插件，热推送资源也从 core 依赖收集内容。仅在 `plugins/` 下增加目录不会自动完成这些注册。

**影响。** 此前网页能显示 OpenSkill，是因为开发服务器另行安装了本地插件。未进行同样安装的新环境，不能据此保证默认出现 OpenSkill。当前锁文件也没有同步该新插件，内置分发及其依赖记录尚未完成。

**建议与验收。** 若目标只是本地试验，可以继续使用服务器本地安装；若目标是随 PenguinHarness 默认提供，应同步三个宿主依赖及锁文件，并在干净安装和对应发布产物中验证发现、安装和读取。依赖接入后，还需同步核心测试中写死的插件数量及 RSI 列表。

**改动范围。** `packages/core/package.json`、`packages/cli/package.json`、`packages/desktop/package.json`、`pnpm-lock.yaml` 及相关测试，均超出此前插件改动范围。

证据：[插件加载器](../../packages/core/src/plugins/index.ts)中的 `pluginRoots`、`installedPluginRoots`；[热推送资源收集](../../scripts/library-payload.mjs)中的 `libraryPayload`；三个宿主的依赖声明。

### OS-05 文档和目录同步检查未通过

**10 月 13 日复测结果。** 中文、英文技能文档均缺少 OpenSkill 条目，导致 `skills-sync.test.ts` 的两项断言失败；官网 `RSI_TOOLKITS` 列表缺少 OpenSkill，导致 `rsi-stats.test.ts` 的一项断言失败。本次仅更新报告，未重新执行这些检查。

**影响。** 当前已经存在三个确定的测试失败，不能将集成描述为“检查全部通过”。此外，核心插件测试虽然通过，但其中内置库测试仍按已注册依赖加载；其通过不能证明 OpenSkill 已进入默认分发。

新增 Python 单元测试目前需单独运行，插件清单没有 `test` 脚本，根目录的 `pnpm test` 也没有显式调用这些 Python 测试。因此，本次手动验证通过不等于后续默认测试会持续覆盖解析器。

**建议与验收。** 补齐双语技能文档和官网算法目录，复测失败项；内置接入后同步 README 插件表、相关说明、测试预期及双语变更记录。为 Python 测试确定持续执行入口和运行环境。验收要求是相关检查实际通过，并保留解析器回归测试的执行结果。

**改动范围。** 已确认需要修改 `packages/docs/content/skills.zh.md`、`skills.en.md` 和 `packages/landing/src/lib/rsi-stats.ts`。其他文档、测试与自动化配置应随发布范围确定。

证据：[文档同步测试](../../packages/docs/test/skills-sync.test.ts)、[官网目录测试](../../packages/landing/test/rsi-stats.test.ts)、[核心插件测试](../../packages/core/test/plugins.test.ts)、[Python 单元测试](tests/test_virtual_results.py)及[插件清单](package.json)。

### OS-06 适配差异会影响结果解释

当前差异已记录在插件来源说明中。这些差异不应全部算作实现错误，但需要在实验报告中明确，部分还需要独立验证。

| 项目 | 当前实现或默认值 | 对验收的影响 |
| --- | --- | --- |
| 多任务部署 | 所有 Case 的技能合并到一个 Target 技能库，按公开适用范围选择；上游按任务部署独立技能集合 | 需要验证误选技能、范围重叠和额外上下文的影响；建议先验收单 Case |
| 模型与检索 | 使用 PenguinHarness 配置的模型及可用研究工具 | 必须记录实际模型和工具，不能声称与论文端点完全一致 |
| 执行环境 | 使用工作区或已配置沙箱，未默认复刻上游每任务容器 | 需记录工具版本、隔离能力及练习环境与正式环境的差异 |
| 正式评估次数 | 冒烟配置每 Case 运行 1 次，论文采用 5 次 | 单次结果不足以衡量随机波动；效果评估应明确重复次数 |
| 构建预算 | 默认每 Case 30 分钟；定向检索最多发出 3 次请求 | 与上游内部 episode 限制及按成功检索计数不同，会影响成本和终止位置 |

另有一项容易误读的行为：当前实现保留上游的重试顺序，在第三次虚拟验证失败后允许再次修订，然后直接导出。因此，最后导出的技能可能没有再次接受虚拟验证。记录必须分别注明“最终版本”和“最后一次受测版本”，不能把前一版本的通过率标到最终版本上。这是所核查上游实现的行为，不是已确认的移植错误；若追加一次最终虚拟验证，应作为新的适配声明并计入预算。

来源说明还记录了论文附录 F 与正文关于 GT pass/fail 信号的一处表述冲突。当前移植选择遵循正文及所核查代码的 OpenSkill 路径：构建阶段不使用任何目标评分信号。后续方法对齐应保持这一口径，或显式批准协议变更。

证据：[来源与适配说明](skills/openskill-rsi-toolkit/references/source-notes.md)、[虚拟评估的重试顺序](skills/openskill-rsi-toolkit/references/virtual-evaluation.md)。

### OS-07 技能已加载，但只有一半 Case 读取了对应技能

**事实。** 最终轮全部 10 个 Target trace 的 `session_meta.system_prompt` 均包含读取 OpenSkill 技能库的指令，并列出了 `openskill-library`。技能文件也已进入正式环境。实际工具调用显示：Case 001、002、004、006、007 读取了对应技能；Case 009 只读取入口 `SKILL.md`；Case 003、005、008、010 没有读取技能文件，直接自行解题。

**原因与影响。** 当前读取步骤依靠 Agent 遵循提示，没有将“已选择并读取适用技能”作为独立可检查的执行条件。文件部署成功不能证明技能已被使用；这次总分混合了使用和未使用技能的执行，不能将每个 Case 的成败都归因于学习后的技能。以 Case 003 为例，Target 直接读取任务及原始数据，编写自己的权限生成脚本，全程未读取技能。

**建议与验收。** 在独立运行记录中保存技能入口、选择结果和实际读取证据；缺少必要步骤时明确报告协议偏差。验证所选技能确实与公开任务匹配，并记录后续是否执行了其程序。不能在已看到目标得分后悄悄重跑、挑选读取了技能的结果。

**范围。** 优先评估插件的部署和评测入口能否提供确定的技能引导及使用审计；若需要宿主在运行时强制执行，应单独评估 core/server 改动。

证据：[Case 003 最终 Target trace][trace-target-003]；[技能库入口][library-reader]；[最终评分矩阵][matrix-final]所引用的 10 个 trial 的 Target trace。

### OS-08 Case 004 字段语义与评分要求不一致，公开契约有歧义

**事实。** 生成的 `normalize_and_rank.py` 在第 37 行将 `rate_shock_bp` 固定写成 `TARGET_BP`，其值为 100。技能自检也要求该字段为 100；独立虚拟测试 `test_rate_shock_bp_is_100_in_every_row` 同样断言每行等于 100。正式评分则要求 APTV 为 25、PWR 为 50，二者最终都输出 100，触发硬性检查失败。

**原因与归因边界。** Creator、自检程序及独立 Verifier 对字段采用了同一种解释，因此 59/59 虚拟通过没有发现正式评分中的语义差异。进一步检查公开任务后发现：正文要求将利息影响标准化到 100 bp，JSON 形状示例又直接给出 `"rate_shock_bp": 100.0`，没有明确区分该字段代表原始冲击还是标准化冲击。因此，这项失败需要同时审查 Benchmark 的公开契约，不能只归为模型计算错误。

**影响。** 最终产物的公司集合、排序和差值已通过相应评分项，内部加权分由 0 升至 55.56%，但两个字段失败使整体 reward 仍为 0。这里既暴露了虚拟验证的共同语义误解，也暴露了任务说明需要澄清的地方。

**建议与验收。** 先明确原始冲击与标准化冲击各自对应的字段，核对公开说明、示例和评分器的一致性，再在清晰契约下验证生成及检查逻辑。修改 Benchmark 属于评测标准变更，需另行确定版本与对照方式；本次原始结果保留，不追溯改分。

证据：[生成脚本][case004-generator]第 37 行；[虚拟测试][case004-suite]第 224 行；[公开任务][case004-instruction]第 21、39 行；[正式评分明细][case004-score]。

### OS-09 已识别的关键覆盖缺口未阻止成功终止

**事实。** Case 003 的 Verifier 在诊断中指出，练习产物将管理员推断为超级管理员，对 14 个权限单元格作了宽松扩展，而该规则不存在于输入文件；它建议补充实际证据或收敛权限。该问题被列为未计入评分的判断风险，没有写入失败断言。Controller 随后按 60/60 将任务结束原因设为 `surrogate_pass`。

**原因与影响。** 协议要求通过率、技能结构和关键需求覆盖共同满足成功条件；本次执行主要依据已编写测试的通过率，对诊断中尚未解决的必需内容没有设置相应限制。因此，“全部测试通过”不能解释为“全部任务要求已被验证”。正式 Case 003 还存在 OS-07 的未读取技能问题，不能将最终失败只归因于虚拟验证。

**建议与验收。** 将断言结果与需求覆盖状态分开记录，要求每项关键需求有独立依据或明确的未验证状态。发现无证据支持的权限扩展时，应基于公开规则处理；如果规则确有歧义，记录受限结论，不能宣称覆盖完整。不得通过查看正式 rubric 补齐构建期答案。

证据：[Case 003 虚拟诊断][case003-diagnosis]第 43 行起；[虚拟评估协议](skills/openskill-rsi-toolkit/references/virtual-evaluation.md)中的成功终止条件。

### OS-10 练习容器路径进入了正式部署技能

**事实。** 40 个生成技能中有 32 个 `SKILL.md` 引用 `/opt/openskill-skills/...`。这是本次 `practice.sh` 使用的练习挂载路径，正式 Harbor 环境中的技能实际位于 Agent State 的 `skills/openskill-library/tasks/...` 下。Case 001、007 的 Target trace 已出现该路径不存在的错误；Case 006 也重新定位了技能文件。

**原因与影响。** 冻结检查没有拦截依赖练习目录的命令示例。部分 Target 自行找到正式路径后继续执行，因此本次并非所有受影响任务都失败；但技能可执行性依赖模型临场修补，增加了工具调用、耗时和放弃使用技能的可能性。

**建议与验收。** 技能引用应相对自身目录解析，或使用正式部署时明确提供的路径。冻结前检查绝对路径、必需脚本及相对链接，并在正式目录布局下做入口检查。该检查不应调用目标评分器。

**范围。** 优先在插件的技能生成约束、冻结校验和部署检查中处理。

证据：[Case 001 路径报错 trace][trace-target-001]第 50 行；[Case 007 路径报错 trace][trace-target-007]第 56 行；本次冻结的 [library][library-index] 中的技能文件。

### OS-11 产物完成后持续检查直至超时，最终报告未披露

**事实。** Case 010 在 05:13:37 已运行脚本并输出后来通过评分的主要统计结果。随后进行了慢 SQL 查询、重复等待和交叉验证，05:18 左右终止过一个慢查询，之后又持续运行 SQL 检查，最终触及 900 秒限制。底层元数据为 `timed_out: true`、`status: timeout`，记录的 Agent 墙钟时间约 902 秒。

**原因与影响。** Target 缺少完成交付后的检查预算和停止策略。已有产物通过了评分，所以 Harbor reward 为 1，评测 worker 返回协议 `status: ok`；这一状态表示评分有效，不表示 Agent 正常结束。Controller 最终报告只呈现有效评分，遗漏了超时。100 分有原始评分依据，但不能据此报告执行完全正常。

**建议与验收。** 对追加检查设置剩余时间预算和终止条件；完成必要交付与验证后及时结束。分别报告评分状态、执行结束状态和异常原因。审计摘要应明确列出超时，即使任务产物获得满分。

**范围。** 插件报告可先读取并披露现有 trial 元数据；若要在评估中心直接展示新的状态字段，需另行评估共享评测协议、存储及 Web 展示的改动范围。

证据：[Case 010 Target trace][trace-target-010]第 52 行起；[Case 010 原始运行结果][case010-result]。

### OS-12 验证修复、实际尝试和重试预算记录不一致

**事实。** Case 007 的 Verifier trace 至少记录了四次完整验证：24/28、26/28、27/28、28/28。前几次修复了验证器的文本提取、引用归属等问题；最终摘要只呈现 27/28 后修订一次达到 28/28。多次尝试复用了 `round-0` 下的报告路径，没有为每次测试版本单独保存完整记录。

**原因与影响。** 执行过程把部分 Verifier 修复当作轮次内部校准，没有完整计入控制器的重试记录。当前协议明确规定 Verifier 错误也消耗预算，默认最多三次验证尝试，因此本次记录及执行与声明口径不一致。修复错误测试本身合理；缺少统一计数和完整历史会使计算投入与终止条件难以复现。

**建议与验收。** 分别记录技能修订号、测试套件版本、执行尝试号和累计预算；每次运行保留独立日志、JUnit、套件哈希及修改原因。若决定将测试开发与技能修订分设预算，应明确声明方法适配并统一执行，不能只在结果摘要中省略失败尝试。

证据：[Case 007 Verifier trace][trace-verifier-007]第 144、198、239、294 行；[虚拟评估协议](skills/openskill-rsi-toolkit/references/virtual-evaluation.md)第 93 行。

### OS-13 实验记录已报错未修复，用量与完成报告不完整

**事实。** 主 trace 在 04:17:34 已记录 `experiment.yaml` 的 `yaml.scanner.ScannerError`：第 29 行未引用的 `Per-Case: ...` 导致标准 YAML 解析失败。最终文件仍存在该问题，Controller 却报告实验记录已完成并验证。

最终报告还称 Token 用量不可获取，而主 trace 的最后一条 `token_usage` 事件记录：`cache_read=20242176`、`cache_write=166343`、`output=215167`、`total=20623686`。这些是主 Controller 会话的累计量，包含大量重复缓存读取，既不是所有子会话与 Target 的总用量，也不能直接当成全部新增输入或总费用；但它证明存在可进一步汇总的用量证据。

**原因与影响。** 收尾流程检查了评分矩阵和状态哈希，没有确保实验记录可解析、异常完整披露、用量统计覆盖明确。下游自动读取会失败；只报告 Target 的正式推理成本会遗漏研究、创建、Verifier 和调度成本。

**建议与验收。** 写入 YAML 后立即解析并校验必要字段，收尾时再次执行；遇到失败不得报告记录完整。按会话关系去重汇总构建与评测用量，标明未知项和计价范围，区分缓存读取、输入和输出。报告应同时包含评分、执行异常、使用覆盖和记录校验状态。

**范围。** 可先在插件内补充记录生成、校验及汇总脚本。本次记录作为原始审计证据保留，后续勘误应有单独说明。

证据：[实验记录][experiment]第 29、31 行；[主 Controller trace 第二部分][trace-main-2]第 113、741、742 行。

## 四 2026 年 10 月 14 日评估结果与证据边界

### 实验配置及实际阶段

| 项目 | 本次取值 |
| --- | --- |
| 优化 Agent / Target | `openskill_controller` / `openskill_target` |
| Benchmark | `penguinharness-benchmark-sec-a`，全部 10 个 Case |
| 模型 | 构建记录为 `deepseek/deepseek-flash`；正式评测同一模型，`thinking_level: medium` |
| 正式重复次数 | 每个版本每个 Case 各 1 次，共 20 次 Harbor trial |
| 构建产物 | 40 个技能，每 Case 4 个；合并部署到一个技能库 |
| 开始与结束 | 03:34—05:29 UTC，约 1 小时 55 分钟 |
| 冻结 | 04:15:22，全部 Case 构建结束后冻结 |
| 基线阶段 | 04:17—04:51，恢复无学习技能的 v1 后评测 |
| 最终阶段 | 04:51—05:29，恢复冻结的 v2 后评测 |
| 结束状态 | 保留 v2，94 个文件；重新计算的状态哈希与记录一致 |

v2 曾在冻结后、测量基线前部署并保存快照，然后恢复 v1 进行基线评测。原会话中“baseline was measured before deployment”的表述不准确；正确顺序是“先冻结与保存两个状态，再依次恢复和测量”。这不改变基线无学习技能的事实。

### 逐 Case 结果

正式分数按共享评测协议采用 `reward × 100`。内部加权评分与整体通过奖励不同；失败 Case 可能有部分评分项通过，仍得到正式分 0。

| Case | 任务 | 最终虚拟检查 | v1 | v2 | v2 技能读取证据 |
| --- | --- | --- | --- | --- | --- |
| 001 | 支付费率匹配 | 49/49 | 100 | 100 | 读取对应技能 |
| 002 | 财务表格份额变化 | 24/24 | 0 | 100 | 读取对应技能 |
| 003 | 淘宝角色权限配置 | 60/60 | 0 | 0 | 未读取技能文件 |
| 004 | 利息费用敏感性分析 | 59/59 | 0 | 0 | 读取对应技能 |
| 005 | 会员等级标准化 | 38/38 | 100 | 100 | 未读取技能文件 |
| 006 | 工作底稿转置 | 49/49 | 100 | 100 | 读取对应技能 |
| 007 | 尽职调查差异备忘录 | 28/28 | 100 | 100 | 读取对应技能 |
| 008 | 跨来源应用情感分析 | 36/36 | 100 | 100 | 未读取技能文件 |
| 009 | 远程办公调查统计 | 28/28 | 100 | 100 | 只读取技能库入口 |
| 010 | F1 超车审计 | 55/55 | 100 | 100 | 未读取技能文件；执行超时 |
| 合计 / 均分 | 10 个 Case | 426/426 | 70 | 80 | 5 个 Case 读取对应技能 |

Case 002 的基线答案为 `0.0003`，超出绝对误差容限 `0.000005`；技能版本输出 `0.000320870622`，通过检查。对应技能要求精确计算并在最后舍入，trace 确认 Target 读取并执行了这些技能。本次唯一新增通过由此产生，尚无重复实验估计其稳定性。

Case 003 的权限表匹配项由 38/45 变为 39/45，但关键规则未全部满足，内部加权分仍为 20%，整体分保持 0。Case 004 的内部加权分由 0 升至 55.56%，整体分仍为 0，具体契约问题见 OS-08。

### 成本、耗时与恢复的故障

| 指标 | 基线 v1 | 技能版本 v2 |
| --- | --- | --- |
| 10 个 Case 的 Target 模型成本合计 | $0.175311 | $0.219589 |
| 单 Case 平均 `agent_execution` 时间 | 210.65 秒 | 246.46 秒 |

正式 Target 模型成本合计 $0.394900；技能版本成本增加约 25.3%，平均执行时间增加约 17.0%。这不是整场实验总成本，不含 Controller、研究、技能创建、虚拟验证及基础设施；平均执行时间也不是包含安装和调度的实验墙钟时间。

Trace 还出现了搜索引擎反爬、宿主 Python 缺少依赖、路径拼写错误、一次后台子 Agent 数量超过上限，以及一次 worker 回复需要去除 Markdown 代码围栏。这些故障后续恢复。格式修复使用同一结果，没有为此重跑 Target；20 个正式 trial 均有有效评分。恢复的工具错误不能全部视为任务失败，但应作为执行开销和工程改进依据。

## 五 历史自动化检查记录

以下检查于 2026 年 10 月 13 日在上述 worktree 重新执行。未运行整个仓库的完整 CI 链路。

| 检查 | 结果 | 证据边界 |
| --- | --- | --- |
| web：`vitest run` | 319 个文件通过，3829 项通过、1 项跳过 | 包含提示词测试的 34 项检查，覆盖中英文 OpenSkill 分支及其他方法；不证明真实 Agent 遵守协议 |
| web：`tsc --noEmit -p tsconfig.json` | 通过 | 验证本次修改的类型一致性 |
| `python3 -B -m unittest discover -s plugins/openskill-rsi-toolkit/tests -v` | 10 项通过 | 验证虚拟结果解析行为，不验证生成测试的语义正确性 |
| core：`vitest run test/plugins.test.ts` | 41 项通过 | 验证插件基础设施及现有断言，不证明新插件已内置 |
| docs：`vitest run test/skills-sync.test.ts` | 1 项通过，2 项失败 | 两种语言的技能文档均遗漏新插件 |
| landing：`vitest run test/rsi-stats.test.ts` | 5 项通过，1 项失败 | 官网 RSI 目录遗漏新插件 |

Vitest 命令分别在对应 package 目录执行。解析器测试包括正常结果、断言失败、跳过、空报告、重复测试、执行错误、退出码不一致及测试数量限制等情况。

## 六 处理顺序与会议决策

1. **先保证实验可解释。** 优先处理 OS-07 的技能读取检查、OS-08 的输出契约和 OS-09 的需求覆盖；同时落实 OS-02 的文件隔离及 OS-12 的预算计数。既有评分和冻结产物作为原始证据保留。
2. **再完善运行与收尾。** 修复 OS-10 的路径可迁移性，补充 OS-11 的停止策略及超时披露，完成 OS-13 的记录解析和用量汇总。验收时应能从报告追溯实际技能使用、每次验证和运行异常。
3. **区分改动范围。** 生成与冻结检查、记录校验可优先在插件内设计；强制工具权限、共享状态协议或页面展示可能涉及宿主。Case 004 的公开说明与评分标准属于 Benchmark 变更，应单独决策。OS-04、OS-05 的默认分发和发布同步仍需另行安排。
4. **确定下一轮实验口径。** 对同一冻结库重复运行可测波动；利用已知分数修改后再评测，应标明已使用反馈。新的无目标监督构建需干净上下文和适当的任务划分。明确模型、重复次数、构建预算及费用统计范围后，再评估稳定增益。

本次报告更新确认了端到端运行和单次分数差值，没有将任何新发现标为已经修复。历史自动化检查、真实任务结果和论文方法对齐是三个独立验收维度。

## 七 参考资料与本机证据索引

- [OpenSkill 论文 v1](https://arxiv.org/abs/2606.06741v1)：方法定义及附录中的执行细节。
- [OpenLAIR/OpenSkill 已核查代码版本](https://github.com/OpenLAIR/OpenSkill/tree/84ca182da055fafb6453dcec4a6defdbbfd987c1)：本次移植使用的上游依据。
- [PenguinHarness OpenSkill 主 Skill](skills/openskill-rsi-toolkit/SKILL.md)：当前执行协议与阶段约束。
- [来源与适配说明](skills/openskill-rsi-toolkit/references/source-notes.md)：论文歧义、上游行为及本地适配记录。
- [评估会话](http://localhost:7365/chat/session-2026-10-14-03-34-26-e6971672)：本次控制会话；需运行对应本地服务。
- [实验记录][experiment]、[冻结清单][freeze]、[最终状态清单][state-final]：记录配置、冻结和部署证据；实验 YAML 的解析问题见 OS-13。
- [正式记分板][scoreboard]、[基线矩阵][matrix-baseline]、[最终矩阵][matrix-final]：20 个原始 trial 的映射及正式评分。
- [主 trace 第一部分][trace-main-1]、[第二部分][trace-main-2]：控制器操作、派发、恢复、汇总及用量事件。

以下证据链接指向本机开发数据目录，JSONL 行号以原始文件为准。文中的执行事实依据工具调用、输出、事件和持久化产物核查，不以会话结尾的自述作为唯一依据。

[trace-main-1]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/traces/2026-10-14/session-2026-10-14-03-34-26-e6971672_001.jsonl
[trace-main-2]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/traces/2026-10-14/session-2026-10-14-03-34-26-e6971672_002.jsonl
[scoreboard]: /home/qx/.penguin/dev-data/default_project/benchmarks/penguinharness-benchmark-sec-a/scoreboard.yaml
[matrix-baseline]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/matrix/baseline.json
[matrix-final]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/matrix/final.json
[freeze]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/freeze.yaml
[state-final]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/state/v2.json
[experiment]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/experiment.yaml
[library-reader]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/library/SKILL.md
[library-index]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/library/index.md
[case004-generator]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/tasks/CASE-004-finlongdocqa_interest_expense_sensitivity_screen_hard/skills/shock-normalization-and-ranking/scripts/normalize_and_rank.py
[case004-suite]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/tasks/CASE-004-finlongdocqa_interest_expense_sensitivity_screen_hard/verify/round-0/suite.py
[case004-instruction]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/tasks/CASE-004-finlongdocqa_interest_expense_sensitivity_screen_hard/input/instruction.md
[case004-score]: /home/qx/.penguin/dev-data/default_project/benchmarks/penguinharness-benchmark-sec-a/.jobs/CASE-004-finlongdocqa_interest_expense_sensitivity_screen_hard-run1-20261014T045800Z/finlongdocqa_interest_expense_se__UKYtTse/verifier/score.json
[case003-diagnosis]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/scratchpad/session-2026-10-14-03-34-26-e6971672/openskill-rsi-toolkit/20261014T033639Z-openskill_target/tasks/CASE-003-workspacebench_taobao_permissions_hard/verify/round-0/diagnosis.md
[case010-result]: /home/qx/.penguin/dev-data/default_project/benchmarks/penguinharness-benchmark-sec-a/.jobs/CASE-010-spider2lite_f1_overtake_audit_hard-run1-20261014T051143Z/spider2lite_f1_overtake_audit_ha__XF2Pt2a/result.json
[trace-verifier-007]: /home/qx/.penguin/dev-data/default_project/agents/openskill_controller/traces/2026-10-14/session-2026-10-14-03-59-14-c00f3f6e_001.jsonl
[trace-target-001]: /home/qx/.penguin/dev-data/default_project/benchmarks/penguinharness-benchmark-sec-a/.jobs/CASE-001-dabstep_real_fees_1681-run1-20261014T045314Z/dabstep_real_fees_1681__8twRaTp/agent/penguin/traces/default_agent/2026-10-14/session-2026-10-14-04-54-25-e453a62d_001.jsonl
[trace-target-003]: /home/qx/.penguin/dev-data/default_project/benchmarks/penguinharness-benchmark-sec-a/.jobs/CASE-003-workspacebench_taobao_permissions_hard-run1-20261014T045321Z/workspacebench_taobao_permission__PFAZSVV/agent/penguin/traces/default_agent/2026-10-14/session-2026-10-14-04-54-30-cca5962b_001.jsonl
[trace-target-007]: /home/qx/.penguin/dev-data/default_project/benchmarks/penguinharness-benchmark-sec-a/.jobs/CASE-007-harveylab_reps_diligence_discrepancy_hard-run1-20261014T050243Z/harveylab_reps_diligence_discrep__fRt6Mb6/agent/penguin/traces/default_agent/2026-10-14/session-2026-10-14-05-03-53-840686bc_001.jsonl
[trace-target-010]: /home/qx/.penguin/dev-data/default_project/benchmarks/penguinharness-benchmark-sec-a/.jobs/CASE-010-spider2lite_f1_overtake_audit_hard-run1-20261014T051143Z/spider2lite_f1_overtake_audit_ha__XF2Pt2a/agent/penguin/traces/default_agent/2026-10-14/session-2026-10-14-05-13-08-7d2366bd_001.jsonl
