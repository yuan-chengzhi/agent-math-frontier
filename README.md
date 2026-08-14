# Agent Math Frontier

面向数学 research agent 的开放问题候选池与证据账本。项目不追求“收录最多”或“AI 解题数”，而是回答四件事：题目为什么适合当前 agent、产物怎样独立验证、问题是否仍开放、即使没有完全解决哪些部分进展仍有价值。

截至 **2026-08-14**，首版包含：

- 17 张人工问题卡：6 题有固定 Lean theorem skeleton，8 题尚无完整形式化但有精确可执行终检，3 题仍需 CAS/领域专家审核；
- 9 题进入“优先审核”，**0 题直接宣称可开跑**；
- 1,217 条 Erdős Problems 元数据，以及 Formal Conjectures 中 1,301 个 `research open` 声明的可再生快照；
- 5 个隔离案例，用来保存状态冲突、变体歧义和刚发生的解决声明。

## 先看哪里

- [优先审核清单](catalog/shortlist.md)：九个不同轨道的候选，不做总排名。
- [已有明确形式化](catalog/machine-formalized.md)：完整目标存在于固定 proof-assistant revision。
- [尚无完整形式化](catalog/not-machine-formalized.md)：继续区分精确 checker 与人工/CAS 审核。
- [完整问题卡](catalog/problem-cards.md)：目标、证书、硬门槛、九维向量和风险。
- [方法](METHODOLOGY.md)：怎样定义“适合 agent”，以及怎样防止选题固化。
- [独立评审记录](docs/independent-review-2026-08-14.md)：三条独立调研怎样改变首版。
- [隔离项](catalog/quarantine.md)：为什么数据库标签或 Lean 文件不能单独作为依据。

当前最适合做首轮基础设施试点的三条路线是：

1. 三正则 girth-13 cage 上界：找少于 272 顶点的图；
2. degree–diameter `(3,9)`：找超过 600 顶点的图；
3. stretched Littlewood–Richardson 负系数反例。

它们覆盖两个记录优化任务和一个有界反例任务，候选证书都小、终检都确定。强正则图 `(69,20,7,5)`、Erdős #23/#307/#835 与 AIM #49/#60 同处优先审核层，但依赖不同的状态、语义或 verifier 准备工作。

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

GitHub Actions 会每周检查上游整库漂移，并在每月 1 日、15 日排入一张独立 portfolio-review 工单。工单只是要求一个与 solver 分离的 agent/reviewer 开始审计，不会把定时任务冒充已完成评审。

## 仓库层级

```text
data/upstream/     可再生 raw 索引，不等于开放或适合
data/problems.json 人工精选问题卡，是判断的唯一数据源
catalog/           面向阅读的自动生成视图
docs/              独立审计与决策记录
scripts/           同步、校验与渲染
```

任何“已解决”结果都先进入 `candidate result`，再经过题意、正确性、新颖性与数学意义的独立审核；solver 不能兼任最终 reviewer。

## 数据来源

主要入口包括 [Erdős Problems](https://www.erdosproblems.com/)、[Formal Conjectures](https://github.com/google-deepmind/formal-conjectures)、[OEIS Open Problems](https://arxiv.org/abs/2608.11941)、[FrontierMath Open Problems](https://epoch.ai/frontiermath/open-problems)、[AIM 2026 AI and Number Theory](https://aimath.org/pastworkshops/aint26.html)、[House of Graphs cage table](https://houseofgraphs.org/meta-directory/cages) 和 [degree–diameter record table](https://web.mat.upc.edu/francesc.comellas/delta-d/taula_delta_d.html)。完整角色、快照和许可说明见 [题源表](catalog/collections.md) 与 [NOTICE](NOTICE.md)。
