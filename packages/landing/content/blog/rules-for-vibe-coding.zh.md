---
title: "如何在 vibe coding 时候立住规矩，写出来的代码不烧心"
date: 2026-10-19
category: perspectives
excerpt: "在 vibe coding 中维护不断增长的项目，需要把关键规则写进仓库文档，集中到共享接口与实现，并用自动化测试持续检查相应行为。"
---

项目功能越多，一次局部改动需要兼顾的原有要求就越多。Coding Agent 处理当前任务时，上下文里往往缺少早期的设计决定和模块依赖。眼前的改动哪怕能跑通，也可能无意间破坏其他模块依赖的规则。

**要让项目规则在持续迭代中立住，团队需要把长期设计要求写进代码仓库，并落实到共享实现、运行时检查与自动化测试中**。本文选用 PenguinHarness 现有的三处代码与测试作为案例，说明如何把具体规则分别落实到写入入口、审批入口和共享实现中。

## 为什么只在对话里交代要求不够

单次会话的上下文容量有限，这些具体规则和原有项目约定往往不在当前上下文内。Agent 修改局部功能时，可能缺少相关的早期设计决定。如果只在某次对话的提示词里临时交代要求，这些聊天内容不会自动成为后续会话可依赖的项目规则。

我们认为，团队应当把长期设计要求和原因保存在仓库文档（例如 `AGENTS.md`）中。不同工具加载规则文件的约定不同。开启新会话时，开发者需要按所用工具的机制加载文档，或在任务指令中明确要求 Agent 先阅读相关文档，为代码修改提供稳定的判断依据。

即便 Agent 读到了仓库文档，文字说明本身也只能引导模型推理。文档无法在代码运行时自动拦截违规调用，也不能阻止后续提交在修改其他功能时意外改坏原有实现。单纯把文档放进仓库，不等于规则已经生效。

**一条真正有用的项目规则，需要写清楚应当保留的行为、制定原因，以及对应的代码实现与验证入口**。

## 项目规则如何落实到代码与测试

明确了代码实现与验证入口，规则才能从文档走向实际执行。仓库文档解释设计意图，共享代码统一具体行为，运行时检查在实际调用时直接拒绝已覆盖的违规操作，自动化测试则在执行测试时核对其覆盖的行为是否发生退化。**只有让会话读取文档、让调用经过共享代码路径，并实际运行测试，这套配合才会真正发挥作用**。

为了合理分配开发者的时间，我们的判断是用一个三层金字塔来安排团队的审查注意力与代码职责。金字塔顶层是少量需要人工仔细审定的核心规则，临时性的任务细节无需全部写进长期规则。中间层是代码调用必须经过的稳定接口与入口，底层则是大量的具体实现与组件。

同一条规则会贯穿这三层，自动化测试则用来核对它们配合后的实际行为。以保留会话历史这条约定为例，顶层规则写明历史记录不可原地改写，中层规定统一的写入入口，底层代码完成文件追加，测试则直接检查写入后的文件状态[^1]。即便有了测试，底层涉及数据变更或权限的改动依然需要人工审查。

<figure class="post-figure" data-figure="vibe-rules-three-layers"><svg class="fig-svg" viewBox="0 0 560 450" role="img" aria-labelledby="rules-for-vibe-coding-vibe-rules-three-layers-zh-title"><title id="rules-for-vibe-coding-vibe-rules-three-layers-zh-title">展示核心规则、稳定接口与入口、具体实现与组件三层金字塔及自动化测试配合关系的示意图。</title><defs><marker id="rules-for-vibe-coding-vibe-rules-three-layers-zh-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" class="fig-arrowhead"/></marker></defs><text x="280" y="26" text-anchor="middle" class="fig-title" style="font-size:22px">规则金字塔与职责分布</text><path d="M120 52H440L468 134H92Z" class="fig-box"/><text x="280" y="83" text-anchor="middle" class="fig-label" style="font-size:22px">核心规则</text><text x="280" y="113" text-anchor="middle" class="fig-label" style="font-size:18px">少量关键约定，人工重点审定</text><path d="M80 148H480L508 230H52Z" class="fig-box"/><text x="280" y="179" text-anchor="middle" class="fig-label" style="font-size:22px">稳定接口与入口</text><text x="280" y="209" text-anchor="middle" class="fig-label" style="font-size:18px">约定调用必经入口，统一检查</text><path d="M40 244H520L548 326H12Z" class="fig-box"/><text x="280" y="275" text-anchor="middle" class="fig-label" style="font-size:22px">具体实现与组件</text><text x="280" y="305" text-anchor="middle" class="fig-label" style="font-size:18px">集中共用逻辑，减少分散修改</text><rect x="60" y="365" width="440" height="72" rx="6" class="fig-link"/><text x="280" y="392" text-anchor="middle" class="fig-label" style="font-size:21px">自动化测试</text><text x="280" y="419" text-anchor="middle" class="fig-label" style="font-size:18px">核对各层配合的实际行为</text><path d="M545 52V326M535 52H545M535 326H545M545 189H552V400H501" class="fig-link"/></svg><ol class="fig-steps"><li>核心规则</li><li>少量关键约定，人工重点审定</li><li>稳定接口与入口</li><li>约定调用必经入口，统一检查</li><li>具体实现与组件</li><li>集中共用逻辑，减少分散修改</li><li>自动化测试</li><li>核对各层配合的实际行为</li></ol><figcaption>规则金字塔用于分配人工审查注意力与代码职责，同一条规则由各层实现共同支撑并由自动化测试核对。</figcaption></figure>

## 用只追加写入保护 Trace 历史记录

**排障和恢复会话依赖完整的历史记录，因此不可原地改写已有记录是三层金字塔顶层的一项核心规则**[^2]。在 PenguinHarness 中，Trace 是保存会话消息与事件的记录，包含工具调用和审批决定，供后续读取历史和恢复会话使用。如果写入代码在原地修改或覆盖已有记录，开发者排障和恢复会话时就会失去可靠的历史依据，因此保护早期记录不被改写是一项核心规则。

为了落实这项规则，PenguinHarness 把 Trace 的写入逻辑放在共享的 `Writer` 中。当有消息需要记录时，`Writer` 以追加模式打开目标文件。它把每条新记录直接写到文件末尾，不会改动文件里已有的内容。当会话需要切换上下文分片时，程序调用 `rotate()` 选择新文件继续写入，不会通过这条写入路径重写旧文件。

针对这一入口行为，测试文件 `trace.test.ts` 直接检查切换前后的文件状态与记录数量[^3]。测试先向第一个文件写入 2 条记录，接着调用 `rotate()` 切换到第二个文件并写入 1 条记录。随后 `trace.test.ts` 核对两个文件路径不同，检查新文件中有 1 条记录，同时原来的文件依然保留着最初的 2 条记录。这项只追加保证针对的是经过 `Writer` 的写入路径，其他具备文件系统权限的外部程序是否直接修改文件属于另一层面的问题。

<figure class="post-figure" data-figure="vibe-rules-rule-path"><svg class="fig-svg" viewBox="0 0 560 404" role="img" aria-labelledby="rules-for-vibe-coding-vibe-rules-rule-path-zh-title"><title id="rules-for-vibe-coding-vibe-rules-rule-path-zh-title">展示 Writer 在旧记录文件追加写入两条记录后，通过 rotate() 切换到新记录文件写入一条记录并由 trace.test.ts 验证的流程图。</title><defs><marker id="rules-for-vibe-coding-vibe-rules-rule-path-zh-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" class="fig-arrowhead"/></marker></defs><rect x="40" y="12" width="480" height="52" rx="6" class="fig-box"/><text x="280.0" y="45.0" text-anchor="middle" class="fig-label" style="font-size:20px">Writer 追加写入</text><path d="M280 65V90" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-rule-path-zh-arrow)"/><rect x="40" y="92" width="480" height="52" rx="6" class="fig-box"/><text x="280.0" y="125.0" text-anchor="middle" class="fig-label" style="font-size:20px">旧记录文件（保留 2 条记录）</text><path d="M280 145V170" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-rule-path-zh-arrow)"/><rect x="40" y="172" width="480" height="52" rx="6" class="fig-box"/><text x="280.0" y="205.0" text-anchor="middle" class="fig-label" style="font-size:20px">rotate() 切换文件</text><path d="M280 225V250" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-rule-path-zh-arrow)"/><rect x="40" y="252" width="480" height="52" rx="6" class="fig-box"/><text x="280.0" y="285.0" text-anchor="middle" class="fig-label" style="font-size:20px">新记录文件（写入 1 条记录）</text><path d="M280 305V330" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-rule-path-zh-arrow)"/><rect x="40" y="332" width="480" height="52" rx="6" class="fig-terminal"/><text x="280.0" y="365.0" text-anchor="middle" class="fig-label" style="font-size:20px">trace.test.ts 验证</text></svg><ol class="fig-steps"><li>旧记录文件（保留 2 条记录）</li><li>Writer 追加写入</li><li>rotate() 切换文件</li><li>新记录文件（写入 1 条记录）</li><li>trace.test.ts 验证</li></ol><figcaption>Writer 通过末尾追加和切换文件保护已写入的会话记录，测试直接核对新旧文件的记录数量。</figcaption></figure>

## 在命令执行入口拦截违规工具调用

除了用 `Writer` 保护已写入的会话记录，系统在模型提出工具调用请求后，也需要先判断这次调用是否获准，通过后才交由执行环境实际运行工具[^4]。**为了避免权限检查散落在各个业务代码中导致前后不一，拒绝规则必须放在进入工具执行前的统一入口上**。

在 PenguinHarness 中，命令策略正是通过会话运行入口 `Session.run` 生效的[^5]。接入 Agent 的应用提供审批决定，命令策略则先检查已启用的拒绝规则。当模型请求的 shell 命令命中已启用的拒绝规则时，策略检查会在询问应用审批之前直接拒绝该命令，命中拒绝规则优先于应用放行。只有当命令未命中拒绝规则时，请求才会继续走后续的审批流程。

为了验证这一入口拦截有效，`command-policy.test.ts` 向真实的会话传入了一个全部放行的审批回调和一个带计数功能的执行环境[^6]。测试中，模拟的模型会请求一条命中禁用规则的 shell 命令。`command-policy.test.ts` 随后核对审批回调的调用次数为 0，执行环境的调用次数也为 0，并且最终返回的消息中包含被策略拒绝的决定。命令策略比对的是 shell 工具的命令文本，用来防止意外误操作。动态计算生成的命令或其他执行方式可能不在它的匹配范围内，运行时的访问隔离则由沙箱边界另外负责。

<figure class="post-figure" data-figure="vibe-rules-interfaces"><svg class="fig-svg" viewBox="0 0 560 446" role="img" aria-labelledby="rules-for-vibe-coding-vibe-rules-interfaces-zh-title"><title id="rules-for-vibe-coding-vibe-rules-interfaces-zh-title">展示模型命令请求在命中命令策略拒绝规则时直接返回拒绝决定，不触发宿主审批和工具执行器的流程图。</title><defs><marker id="rules-for-vibe-coding-vibe-rules-interfaces-zh-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" class="fig-arrowhead"/></marker></defs><rect x="140" y="10" width="280" height="52" rx="6" class="fig-box"/><text x="280.0" y="43.0" text-anchor="middle" class="fig-label" style="font-size:20px">模型命令请求</text><path d="M280 63V91" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-interfaces-zh-arrow)"/><rect x="110" y="94" width="340" height="52" rx="6" class="fig-box"/><text x="280.0" y="127.0" text-anchor="middle" class="fig-label" style="font-size:20px">命令策略检查</text><path d="M280 147V165H140V189" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-interfaces-zh-arrow)"/><path d="M280 147V165H420V189" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-interfaces-zh-arrow)"/><rect x="20" y="192" width="240" height="48" rx="6" class="fig-box"/><text x="140.0" y="222.65" text-anchor="middle" class="fig-label" style="font-size:19px">命中拒绝规则</text><rect x="300" y="192" width="240" height="48" rx="6" class="fig-box"/><text x="420.0" y="222.65" text-anchor="middle" class="fig-label" style="font-size:19px">未命中拒绝规则</text><path d="M140 241V269" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-interfaces-zh-arrow)"/><path d="M420 241V269" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-interfaces-zh-arrow)"/><rect x="20" y="272" width="240" height="48" rx="6" class="fig-terminal"/><text x="140.0" y="303.0" text-anchor="middle" class="fig-label" style="font-size:20px">拒绝决定</text><rect x="300" y="272" width="240" height="48" rx="6" class="fig-box"/><text x="420.0" y="302.65" text-anchor="middle" class="fig-label" style="font-size:19px">进入后续审批流程</text><rect x="20" y="344" width="520" height="88" rx="6" class="fig-link"/><text x="280" y="377" text-anchor="middle" class="fig-label" style="font-size:20px">宿主审批（调用 0 次）</text><text x="280" y="412" text-anchor="middle" class="fig-label" style="font-size:20px">工具执行器（调用 0 次）</text><path d="M140 321V343" class="fig-link"/></svg><ol class="fig-steps"><li>模型命令请求</li><li>命令策略检查</li><li>命中拒绝规则</li><li>拒绝决定</li><li>宿主审批（调用 0 次）</li><li>工具执行器（调用 0 次）</li><li>未命中拒绝规则</li><li>进入后续审批流程</li></ol><figcaption>命中拒绝规则的 shell 命令在策略入口处即被否决，不会调用宿主审批或工具执行器。</figcaption></figure>

## 集中维护重复绘制的共享图标

**命令策略在入口处集中了权限检查，多处共用的界面实现同样需要集中到单一共享文件来维护**。在日常前端迭代中，Agent 或开发者很容易通过复制粘贴快速完成局部界面，却破坏了全局一致性。PenguinHarness 的测试记录显示，代表记忆的大脑图标曾被分别手写在面板、记忆变更卡片和 Agent 卡片这三处代码中[^7]。当开发者重绘其中一处的外观时，另外两处依然保留着旧形状。

为了解决多处修改容易遗漏的问题，PenguinHarness 将这枚记忆大脑图标的定义集中到共享文件 `icons.ts` 中。项目同时规定，该图标的已知 SVG 路径片段只能出现在这个文件里。测试文件 `icon-scale.test.ts` 会扫描前端与组件库的源码，查找记忆大脑图标及其他几个已知图标的 SVG 路径片段。它会核对这些路径片段是否只出现在各自指定的共享文件中。一旦有人在其他组件里再次手写或粘贴这段已知路径字符串，测试就会报错。

这种源码扫描比对的是已知路径字符串，只能抓出对已知图标代码的直接复制，无法识别新画出来的其他视觉相似图标。提取共享代码也需要根据实际复用来定，只有真正被多处共用的实现才值得提取到共享文件中，不必为只用一次的局部细节预先搭建通用框架。

<figure class="post-figure" data-figure="vibe-rules-reuse"><svg class="fig-svg" viewBox="0 0 560 356" role="img" aria-labelledby="rules-for-vibe-coding-vibe-rules-reuse-zh-title"><title id="rules-for-vibe-coding-vibe-rules-reuse-zh-title">展示面板、记忆变更卡片和 Agent 卡片三处位置统一引用共享定义 icons.ts，并由 icon-scale.test.ts 扫描已知图标 SVG 路径片段的结构图。</title><defs><marker id="rules-for-vibe-coding-vibe-rules-reuse-zh-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" class="fig-arrowhead"/></marker></defs><rect x="80" y="10" width="400" height="52" rx="6" class="fig-box"/><text x="280.0" y="43.35" text-anchor="middle" class="fig-label" style="font-size:21px">共享定义 icons.ts</text><path d="M280 63V85H92V113" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-reuse-zh-arrow)"/><path d="M280 63V85H280V113" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-reuse-zh-arrow)"/><path d="M280 63V85H468V113" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-reuse-zh-arrow)"/><rect x="12" y="116" width="160" height="54" rx="6" class="fig-box"/><text x="92.0" y="149.3" text-anchor="middle" class="fig-label" style="font-size:18px">面板</text><rect x="190" y="116" width="180" height="54" rx="6" class="fig-box"/><text x="280.0" y="149.3" text-anchor="middle" class="fig-label" style="font-size:18px">记忆变更卡片</text><rect x="388" y="116" width="160" height="54" rx="6" class="fig-box"/><text x="468.0" y="149.3" text-anchor="middle" class="fig-label" style="font-size:18px">Agent 卡片</text><path d="M92 171V196H468V171M280 171V218" class="fig-edge"/><path d="M280 196V218" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-reuse-zh-arrow)"/><rect x="40" y="220" width="480" height="52" rx="6" class="fig-box"/><text x="280.0" y="253.0" text-anchor="middle" class="fig-label" style="font-size:20px">icon-scale.test.ts 源码扫描</text><path d="M280 273V299" class="fig-edge" marker-end="url(#rules-for-vibe-coding-vibe-rules-reuse-zh-arrow)"/><rect x="20" y="302" width="520" height="46" rx="6" class="fig-link"/><text x="280.0" y="331.65" text-anchor="middle" class="fig-label" style="font-size:19px">已知图标 SVG 路径片段（仅限 1 处）</text></svg><ol class="fig-steps"><li>共享定义 icons.ts</li><li>面板</li><li>记忆变更卡片</li><li>Agent 卡片</li><li>icon-scale.test.ts 源码扫描</li><li>已知图标 SVG 路径片段（仅限 1 处）</li></ol><figcaption>将三处共用的记忆图标集中到单一共享文件并扫描源码，可发现已知图标路径被再次复制粘贴。</figcaption></figure>

## 从实际错误中补齐规则与日常验证

源码扫描只能抓出已知图标路径的再次复制粘贴，说明自动化测试的范围需要随着实际遇到的问题不断维护。测试能够接管大量重复的检查工作，但每个测试只证明它覆盖的具体行为符合预期，测试通过不代表所有未知情况都安全。开发者依然需要把审查精力放在高风险改动上，重点检查设计假设是否合理、权限边界是否严密，以及数据写入方式是否安全。

在日常使用 Coding Agent 迭代项目时，如果发现某类错误重复出现，我们建议先把问题在本地复现出来，明确期望的正确行为。接着修改对应的共享实现或入口检查逻辑，同时更新或补上自动化测试。

改完代码后，先确认测试能报错抓出修改前的问题，再确认修复后测试顺利通过。随后把测试放进日常 CI（代码变更时自动运行的检查）中持续执行。

**项目规则、共享代码与自动化测试需要随着需求变化一起更新**。当后续出现合理的新需求、确实需要调整原有行为时，团队应当在下一次改动中一并审查和修改仓库里的规则文档、代码实现与测试用例。

[^1]: [packages/core/src/trace/writer.ts](https://github.com/Prism-Shadow/penguin-harness/blob/v0.2.18/packages/core/src/trace/writer.ts)
[^2]: [packages/docs/content/sessions-and-traces.zh.md](https://github.com/Prism-Shadow/penguin-harness/blob/v0.2.18/packages/docs/content/sessions-and-traces.zh.md)
[^3]: [packages/core/test/trace.test.ts](https://github.com/Prism-Shadow/penguin-harness/blob/v0.2.18/packages/core/test/trace.test.ts)
[^4]: [packages/docs/content/interfaces.zh.md](https://github.com/Prism-Shadow/penguin-harness/blob/v0.2.18/packages/docs/content/interfaces.zh.md)
[^5]: [packages/core/src/session.ts](https://github.com/Prism-Shadow/penguin-harness/blob/v0.2.18/packages/core/src/session.ts)
[^6]: [packages/core/test/command-policy.test.ts](https://github.com/Prism-Shadow/penguin-harness/blob/v0.2.18/packages/core/test/command-policy.test.ts)
[^7]: [packages/web/test/icon-scale.test.ts](https://github.com/Prism-Shadow/penguin-harness/blob/v0.2.18/packages/web/test/icon-scale.test.ts)
