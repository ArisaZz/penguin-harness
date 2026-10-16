# OpenSkill changes

## 2026.10.16.4

New experiments validate the actual host SDK and configured Session before construction,
then check a runtime fingerprint before each role. A source-archive helper installs and
builds a complete runtime from one commit and frozen lockfile in a fresh directory. This
prevents the observed new-SDK/old-dependency deployment from reaching a creator launch.
The optional `stop_on_recurrence` policy now belongs to the executor: execution failures
stop the batch, while completed virtual assertion failures retain the refinement protocol.
Launcher diagnostics preserve the failure stage and actual process exit code.
Failed official practice cannot register a revision merely because it left output files.
Stopped runs report stopped guidance; container creation is serialized with cancellation.

新实验在构建前检查真实宿主机 SDK 和配置的会话，并在每次角色启动前核对运行环境指纹。
新增部署脚本从固定提交的源码归档和锁文件，在新目录安装、构建完整运行环境，提前拦截
新版 SDK 与旧依赖混用的问题。`stop_on_recurrence` 可选策略由执行器直接执行：执行故障
停止整批实验，已完成的虚拟断言失败继续遵循修订协议。启动诊断保留失败阶段和真实退出码。
正式练习即使留下输出文件，也不能在执行失败后登记修订。停止状态会反映在下一步指引中，
容器创建与取消操作使用同一把锁，防止停止返回后又启动容器。

No model call is made by the runtime probe. Session resumption is tested with the scripted
provider, because an unused Session has no resumable Trace. Existing experiments retain their
recorded Skill version; stopped runs are not resumed or rewritten. Algorithm budgets, role
isolation, final-revision selection and post-freeze evaluation are unchanged. Source changes
are confined to this plugin.

运行环境预检不调用模型。空会话没有可恢复的 Trace，因此会话恢复能力由模拟模型测试验证。
旧实验保留其记录的 Skill 版本，停止的实验不恢复、不重写。算法预算、角色隔离、最后版本
选择及冻结后评测规则保持原样。源码改动仅限本插件。

## 2026.10.16.3

GDPevo construction can use a plugin-owned startup adapter: the service opens its private
log as `taskenv`, without restoring broad container privileges. Initialization preflights
every construction image before creating a journal or calling a model. Each role and
measurement checks identity, mount permissions and, for GDPevo, business API readiness,
private-directory denial and a disabled judge. Failed startup preserves bounded diagnostics
before container removal and prevents the batch from starting construction.

The refinement protocol and final evaluation reference are unchanged. Old experiments stay
on their recorded Skill version; stopped directories are preserved. This is an environment
execution fix and provides no new benchmark score.

GDPevo 构建可使用插件内的启动适配器：业务服务以 `taskenv` 身份打开自己的私有日志，
保留收紧后的容器权限。初始化在创建实验日志或调用模型前检查所有构建镜像。每次角色
和测量执行都检查身份与挂载权限；GDPevo 还检查业务 API 就绪、私有目录不可读和 judge
关闭。启动失败时先保存有大小与时间上限的诊断信息，再清理容器，并阻止整批构建启动。

修订协议与最终评估参考保持原样。旧实验继续使用其记录的 Skill 版本，已停止的目录予以
保留。本次修复解决环境执行问题，不提供新的 benchmark 分数。源码改动仅限本插件。

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
