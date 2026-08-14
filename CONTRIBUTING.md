# Contributing

优先贡献状态证据、精确 verifier、statement fidelity 审核和有意义的部分目标，而不是增加标题数量。

新增候选：

1. 在 `data/sources.json` 登记 canonical source、快照、许可和它在项目中的可信角色；
2. 在 `data/problems.json` 填完整问题卡，尤其是固定目标、成功工件、五个硬门槛、九维向量与不可被高分抵消的风险；
3. 若状态、变体或许可不清，先进入 `data/quarantine.json`；
4. 运行 `make render && make check`；
5. PR 中附两份相互独立的审核：一份重建原意，一份主动寻找“它其实已解决/题目不同”的证据。

不要直接编辑 `catalog/`。不要复制没有明确再分发许可的完整题面或数据。不要把记录改进、有限参数解决、子类排除、文献重发现写成完整问题已解决。
