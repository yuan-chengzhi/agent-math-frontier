# Agent Math Frontier

面向数学 research agent 的开放问题候选池与证据账本。项目不追求“收录最多”或“AI 解题数”，而是回答四件事：题目为什么适合当前 agent、产物怎样独立验证、问题是否仍开放、即使没有完全解决哪些部分进展仍有价值。

截至 **2026-08-14**，首版包含：

- 17 张人工问题卡：6 题有固定 Lean theorem skeleton，8 题尚无完整形式化但有精确可执行终检，3 题仍需 CAS/领域专家审核；
- 14 题已有机器可寻址实验包：6 题绑定固定 Lean 陈述，8 题绑定精确
  executable spec；其中 3 题通过完整审查成为严格 `active`，11 题可作
  未审计的 `experimental_active`；
- 1,217 条 Erdős Problems 元数据，以及 Formal Conjectures 中 1,301 个 `research open` 声明的可再生快照；
- 5 个隔离案例，用来保存状态冲突、变体歧义和刚发生的解决声明。

## 先看哪里

- [优先审核清单](catalog/shortlist.md)：九个不同轨道的候选，不做总排名。
- [已有明确形式化](catalog/machine-formalized.md)：完整目标存在于固定 proof-assistant revision。
- [尚无完整形式化](catalog/not-machine-formalized.md)：继续区分精确 checker 与人工/CAS 审核。
- [完整问题卡](catalog/problem-cards.md)：目标、证书、硬门槛、九维向量和风险。
- [方法](METHODOLOGY.md)：怎样定义“适合 agent”，以及怎样防止选题固化。
- [独立评审记录](docs/independent-review-2026-08-14.md)：三条独立调研怎样改变首版。
- [14 题实验组合](docs/experimental-portfolio.md)：每题实际检查什么、结论边界和运行入口。
- [隔离项](catalog/quarantine.md)：为什么数据库标签或 Lean 文件不能单独作为依据。

当前严格 active target 仍是三条：

1. degree–diameter `(3,9)`：构造至少 601 顶点、最大度数至多 3、
   直径至多 9 的图；
2. Erdős #64：在至多 64 个顶点内寻找避开全部 2 的幂长度环的
   最小度数至少 3 的反例图；
3. stretched Littlewood–Richardson：在冻结的长度/大小界内寻找普通
   单项式基系数为负的精确反例。

它们覆盖记录构造、开放图论反例和代数组合有界反例，并都具有严格的
target-specific executable verifier。为了先实验再决定是否投入完整审核，另有
[`data/experimental-portfolio.json`](data/experimental-portfolio.json)：它精确包含
全部 14 个机器可寻址目标，但不把缺失的独立审核和红队收据冒充已经完成。
因此实验口径是 14/14 active（3 个 `audited_active` + 11 个
`experimental_active`），严格研究结论口径仍只有 3 个 active。
AIM #60 的旧 v1 保留作回归，实验组合选择临时重设到 1455091 门槛的 v2；
其 open-status gate 仍为 `fail`，所以不能被当作已确认的新纪录攻击。

## 这里怎样使用“形式化”

顶层按用户关心的两类展示，但数据层不是布尔值：

| 级别 | 顶层归类 | 含义 |
|---|---|---|
| `proof_assistant` | 已形式化 | 完整目标在固定 Lean/Coq/Isabelle artifact 中；仍要单独审查题意忠实度 |
| `executable_spec` | 未形式化 | 有限候选可被精确程序检查，但整条数学命题没有进入证明助手 |
| `precise_informal` | 未形式化 | 题意精确，验证仍依赖 CAS 证书或领域专家 |
| `research_program` | 未形式化 | 还需冻结参数、子类或里程碑，不能直接攻击 |

Erdős 数据里的 `formalized: yes` 表示**陈述**已有形式化，`formal_status` 则描述**解答证明**的形式化状态；本项目不会混淆两者。

## 为什么没有总分

每题记录九个 0–3 维度：可验证性、反馈密度、表示紧凑性、可拆分性、工具成熟度、部分进展价值、数学价值、开放状态可信度、资源可行性。它们不相加，因为高可验证性不能抵消题意误译，高知名度也不能抵消完全没有反馈。

进入 active queue 前还必须通过五个硬门槛：开放状态可追溯、目标精确、存在独立验证路径、部分进展预先定义、实验可复现。

## 本地使用

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
make check
```

重新抓取两个整库索引并生成页面：

```bash
make sync
```

`data/upstream/` 只镜像简化元数据和声明位置，不复制完整题面。人工判断编辑 `data/problems.json`、`data/sources.json`、`data/precedents.json` 与 `data/quarantine.json`；`catalog/` 由脚本生成。

## 机器可执行的 active 边界

`shortlist` 仍只是人工审核优先级。严格、已审计的攻击面是
[`data/active-portfolio.json`](data/active-portfolio.json)，它由
`scripts/export_active.py` 从完整问题账本和内容寻址 target bundle
确定性导出。当前导出精确包含上述 3 个 active target。

一个问题只有在以下条件全部满足时才能进入该文件：五个 hard gate
均为 `pass`；`targets/<problem-id>/target-bundle.json` 存在；target card、
基线、两份独立审核、evaluator 红队和预算收据均存在、通过严格版本化
schema，并以 SHA-256 绑定到同一 problem/target/verifier。任何缺失、额外
字段、条件性审核、未注册 verifier 或哈希漂移都会令导出失败。

`problem.verification.mode` 是语义能力名（“需要验证什么”），不是程序名。
target card 选择带 `.vN` 后缀的版本化 `verifier_id`（“用哪个不可变实现”）；
注册表所绑定的 manifest 必须用 `binds_verification_mode` 明确声明并匹配该
语义能力。这样可以替换或并行红队多个 checker 实现，而不改写问题定义。

每份 review receipt 必须逐字节绑定完整 review report、problem/target 的
`source_revision`、reviewer authority 记录和 session evidence，并固定声明
其范围仅为身份与流程绑定。它**不证明** reviewer 身份真实、数学判断正确，
也不是密码学签名；这些仍需 host 在接纳时通过外部身份系统和独立复核确认。

```bash
# 只检查已提交导出是否精确、最新
python scripts/export_active.py --check

# 更新 canonical export；不会自动晋升任何问题
python scripts/export_active.py --output data/active-portfolio.json

# 重新核验冻结审查、红队、预算和全部 content bindings
python scripts/prepare_activation.py --check
```

JSON 逻辑身份使用 `scripts/contracts.py` 的 canonical encoding；文件工件
收据绑定原始字节、长度和 SHA-256。JSON 输入与绑定工件均有显式大小上限，
且只接受 repository 内的普通非符号链接文件。版本化 JSON Schema 位于
`schemas/`。

## 先跑的 experimental 边界

`data/experimental-portfolio.json` 是 14 题的实验入口。每题至少具备：冻结
target card、候选 JSON Schema、与问题语义匹配的版本化离线 verifier。其角色分为：

- `audited_active`：3 题，亦存在完整 target bundle；
- `experimental_active`：11 题，已开放给 solver/evaluator 实验，但尚不能据此声称
  最新开放状态、checker 红队和独立题意审核均已通过；
- `verifier_regression_only`：该角色由 schema 保留；当前导出为 0。AIM #60 的旧 v1
  仍在注册表中作回归，但 14 题组合选择 v2 实验目标。

```bash
# 查看 14 个机器入口
python scripts/verify_candidate.py --list

# 按 problem ID 运行内容固定的 verifier
python scripts/verify_candidate.py costas-order-32 candidate.json

# 检查 14 题导出没有哈希漂移或缺件
python scripts/export_experimental.py --check
```

这里的 6 个 `proof_assistant` 项仍只表示原始完整命题有固定 Lean 陈述；当前有限
候选 verifier 与最终 no-sorry Lean 闭合是两个独立阶段。8 个 `executable_spec`
项则没有被改写成“已有证明助手形式化”。

GitHub Actions 会每周检查上游整库漂移，并在每月 1 日、15 日排入一张独立 portfolio-review 工单。工单只是要求一个与 solver 分离的 agent/reviewer 开始审计，不会把定时任务冒充已完成评审。

## 仓库层级

```text
data/upstream/     可再生 raw 索引，不等于开放或适合
data/problems.json 人工精选问题卡，是判断的唯一数据源
data/verifiers.json 可执行 verifier 注册表；空注册表是合法状态
data/active-portfolio.json 唯一 fail-closed active 导出
data/experimental-portfolio.json 14 题机器实验导出
targets/           实验 target card；严格 active 项另有完整 target bundle
schemas/           problem/target/receipt 的严格版本化 schema
catalog/           面向阅读的自动生成视图
docs/              独立审计与决策记录
scripts/           同步、校验与渲染
```

任何“已解决”结果都先进入 `candidate result`，再经过题意、正确性、新颖性与数学意义的独立审核；solver 不能兼任最终 reviewer。

## 数据来源

主要入口包括 [Erdős Problems](https://www.erdosproblems.com/)、[Formal Conjectures](https://github.com/google-deepmind/formal-conjectures)、[OEIS Open Problems](https://arxiv.org/abs/2608.11941)、[FrontierMath Open Problems](https://epoch.ai/frontiermath/open-problems)、[AIM 2026 AI and Number Theory](https://aimath.org/pastworkshops/aint26.html)、[House of Graphs cage table](https://houseofgraphs.org/meta-directory/cages) 和 [degree–diameter record table](https://web.mat.upc.edu/francesc.comellas/delta-d/taula_delta_d.html)。完整角色、快照和许可说明见 [题源表](catalog/collections.md) 与 [NOTICE](NOTICE.md)。
