# 方法：从开放题到可审计的 agent 任务

## 1. “适合”是任务—能力匹配

当前证据最强的默认形态是：候选可紧凑编码，生成后能由便宜、确定的 evaluator 打分，搜索有比最终真假更密集的反馈，结果能转成精确证书。FunSearch、AlphaEvolve、CPro 与形式证明批量实验都支持这一判断；自然语言 research agent 的高价值突破说明仍应保留少数 moonshot，但其专家审核成本远高于生成成本。实证来源见 [catalog/evidence.md](catalog/evidence.md)。

因此，本项目不把以下信号单独视为“适合”：题目短、著名、有奖金、存在 Lean 文件、有限、模型写出了长证明、多个相似模型都同意，或 evaluator 数值有所提升。

## 2. 三层池，而不是一张题单

```text
raw catalog  ──状态/语义/许可审计──>  curated candidates  ──冻结 target card──>  active attacks
     │                                      │                                  │
     └─可过期、可冲突                       └─不是开跑授权                       └─保存全部成本与失败
```

- `raw catalog`：可批量采集题库元数据，允许状态陈旧和重复。
- `curated candidates`：有规范来源、可执行目标、验证路线、风险和部分进展定义。
- `active attacks`：两名独立 reviewer 完成状态/题意审核，evaluator 已红队，预算与工件已冻结。

结果不会直接覆盖题目状态；状态变化以追加事件记录。

## 3. 形式化强度与忠实度分开

`proof_assistant` 必须记录系统、固定 commit、文件、声明名和编译状态。另设 `fidelity`：`unreviewed`、`one_source_checked`、`one_expert`、`two_expert` 或 `disputed`。一个 theorem 能编译，只说明编码后的命题成立，不说明它忠于原题。

没有完整 proof-assistant 陈述的题继续分成：

- `executable_spec`：图、矩阵、排列、整数、多项式等有限对象可精确检查；
- `precise_informal`：目标精确，但仍需 CAS 证书或领域证明审核；
- `research_program`：先拆出参数、子类或可证伪里程碑。

“部分形式化”仍归未形式化，直到定义、量词和完整目标都覆盖。

## 4. 五个硬门槛

精选候选晋升 active 前，每项必须为 `pass`：

1. `open_status`：原始出处、最近核查日期、检索记录与冲突证据齐全；
2. `exact_target`：量词、边界、变体、完整成功和部分成功条件已冻结；
3. `verification_path`：proof assistant、精确/区间证书，或已落实的领域 reviewer；
4. `valuable_partial_progress`：新界、记录、反例、关键引理、形式化或状态清理的价值在运行前定义；
5. `reproducibility`：evaluator、依赖、种子、预算、输出和失败均可保留。

任何 `conditional` 都是未完成工作，不可被高分抵消。

## 5. 九维向量，不求和

每维 0–3，0 表示缺失/很差，3 表示强：

| 维度 | 问题 |
|---|---|
| `verifiability` | 最终核验有多确定、多便宜？ |
| `feedback_richness` | 搜索是否有连续或分层信号？ |
| `representation` | 解能否表示为有限对象、短程序或结构化证明？ |
| `decomposability` | 能否拆成独立局部目标？ |
| `tool_readiness` | Lean/mathlib、SAT/SMT、CAS、数据库是否成熟？ |
| `partial_value` | 没有完全解决时，预定产物仍有多大价值？ |
| `math_value` | 领域专家如何判断重要性？ |
| `status_confidence` | “仍开放”和“原意如此”的证据有多强？ |
| `resource_feasibility` | 在预算内生成与独立复核是否现实？ |

只在同一轨道做 Pareto 比较。例如“刷新图构造纪录”不能与“自然语言高价值证明”用一个总分排序。

## 6. Target card 与审核顺序

每次攻击前固定：

1. canonical statement、变体与来源 revision；
2. 当前最佳界/基线证书及其哈希；
3. 完整成功、部分成功和停止条件；
4. evaluator 源码、测试向量、复杂度和已知漏洞；
5. 模型、scaffold、工具、随机种子、token/时间/算力预算；
6. 预期输出格式与独立 reviewer。

审核顺序是：机器终检 → 边界与 evaluator 对抗审计 → 题意忠实度 → 新颖性检索 → 数学意义 → 可复现性。形式证明禁止残留 `sorry`、隐含未声明公理或把核心难点挪入未证 lemma；数值结果禁止只给浮点。

未形式化的“完整解决”原则上需要两名领域专家。形式化结果仍需要专家确认 statement fidelity。公开结果先标 `candidate_result`，经过冷却期和上游同步才可升级为 `verified_novel_result`。

## 7. 防止选择固化

季度重新评估轨道配额，初始参考为：35% 构造/优化、25% 形式证明、20% 精确未形式化理论题、10% 状态与文献调查、10% 高价值 moonshot。在所有通过硬门槛的候选中保留约 20% 随机探索，不让当前 evaluator 便利性定义全部数学价值。

每两周由与 solver 分离的 agent/reviewer 检查：

- 最近是否有人抢先或上游状态已变；
- 任务是否只因工具熟悉而被反复选择；
- 成功产物是否仍有发表/复用价值；
- 失败和资源消耗是否已触发 kill 条件；
- 新题源是否提供更高期望价值候选；
- 各轨道分母、失败数和人工审核小时是否如实公开。

Hadamard 668 在形式库尚未同步时被 Epoch 临时标为 solved、OEIS Open 的快速批量证明，以及本轮对 symmetric weighing matrix 变体的误判，都是必须持续复核而不能维护静态题单的直接例子。
