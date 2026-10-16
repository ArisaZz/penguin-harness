# OpenSkill changes

## 2026.10.16.2

New experiments use a dedicated executor and isolated SDK role launcher. Creator and verifier
tools run in separate Docker containers; the verifier receives public inputs, independent
anchors and selected outputs. The executor collects actual practice/pytest results, enforces
the collected-test limit, and stops workers on cancellation or deadline. Default practice
resumes the creator with read-only frozen skills; executable tasks may explicitly select
command practice. Existing journals and the final evaluation protocol are unchanged.

The fixed skill plan, persistent creator, feedback and retrieval budgets, final-revision
selection and global freeze remain. Image contents, research provenance and verifier
semantics still require review. This release does not claim a benchmark improvement.

新实验改用专用执行器和隔离的 SDK 角色启动器。Creator 与 verifier 的工具分别运行在独立
Docker 容器内；verifier 只接收公开输入、独立验证依据和列出的结果文件。执行器采集实际
实践及 pytest 结果，在测试执行前检查数量上限，并在取消或到期时终止进程。默认实践阶段
恢复同一个 creator，以只读方式使用冻结技能；可执行任务可显式选择命令模式。旧实验记录
及最终评估协议保持原样。

固定技能计划、持久 creator、反馈与检索预算、最后版本选择、全局冻结规则继续保留。
镜像内容、检索来源和验证语义仍需审查。本次修改不代表已经获得 benchmark 分数提升。

Source changes are confined to this plugin, as requested. Run instructions and the trust
boundary are in [executor.md](skills/openskill-rsi-toolkit/references/executor.md).
按要求，源码改动仅在本插件内；启动方法和隔离边界见上述文档。
