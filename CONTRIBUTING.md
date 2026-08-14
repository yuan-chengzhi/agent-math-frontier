# Contributing

优先贡献状态证据、精确 verifier、statement fidelity 审核和有意义的部分目标，而不是增加标题数量。

新增候选：

1. 在 `data/sources.json` 登记 canonical source、快照、许可和它在项目中的可信角色；
2. 在 `data/problems.json` 填完整问题卡，尤其是固定目标、成功工件、五个硬门槛、九维向量与不可被高分抵消的风险；
3. 若状态、变体或许可不清，先进入 `data/quarantine.json`；
4. 运行 `make render && make check`；
5. PR 中附两份相互独立的审核：一份重建原意，一份主动寻找“它其实已解决/题目不同”的证据。

不要直接编辑 `catalog/`。不要复制没有明确再分发许可的完整题面或数据。不要把记录改进、有限参数解决、子类排除、文献重发现写成完整问题已解决。

## 进入 experimental portfolio

先跑实验不要求伪造完整 active receipts，但至少必须同时提交：冻结且绑定原问题卡
revision 的 `target-card.json`、严格候选 JSON Schema、可离线运行的版本化 verifier
manifest，以及能覆盖边界/恶意输入的测试。`scripts/export_experimental.py` 会自动要求
每一个 `proof_assistant` 或 `executable_spec` 问题都有这些工件，并检查 verifier 的
`binds_verification_mode`。实验角色不等于 novelty 或 statement-fidelity 通过。

## 晋升 active

不要单独把 `stage` 改成 `active`，也不要提交 placeholder reviewer、虚构的
红队结论或只写名字而不能运行的 verifier。晋升 PR 必须同时提供：

1. `targets/<problem-id>/target-card.json` 与 candidate JSON Schema；
2. 冻结基线及其 receipt；
3. 两名不同 reviewer 的 `STATEMENT_FIDELITY` 和
   `OPEN_STATUS_AND_NOVELTY` pass receipts；每份 receipt 必须绑定完整报告、
   source revision、reviewer authority 记录和 session evidence；
4. 已注册、离线、源码内容寻址的 verifier manifest；问题卡中的
   `verification.mode` 是语义能力名，target 的 `verifier_id` 必须是带 `.vN`
   后缀的版本化实现 ID，manifest 的 `binds_verification_mode` 必须匹配前者；
5. 由第三名 reviewer 产生的 evaluator red-team corpus、报告和 pass receipt；
6. 带资源上限、停止条件和失败保留规则的 budget receipt；
7. 把以上文件逐字节绑定起来的 `target-bundle.json`。

所有 JSON 必须符合 `schemas/` 中的 V1 exact schema；`scripts/contracts.py`
还会检查跨文件身份、SHA-256、路径逃逸、reviewer 分离、source revision、
特殊文件和输入大小。Review receipt 只形成可审计的身份/流程与字节绑定，
不构成数学真实性证明、身份认证或密码学签名；晋升者仍须独立核验这些事实。
运行 `make active && make check` 生成并验证唯一的 PMW 输入
`data/active-portfolio.json`。该导出是生成物，不能用手工编辑绕过检查。
