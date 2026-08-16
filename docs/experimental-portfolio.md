# 14 题 experiment-ready 组合

状态日期：2026-08-14。14/14 个目标均为 `experiment-ready`：target、候选格式和
离线终检已经闭合。这个词是阅读层总称，不是新 schema 值，也不表示全部题都完成了
独立题意审查、最新开放状态审查或 verifier 红队。

机器角色只有两类：

- `audited_active`：同时满足严格审核资格；对应 `strict_stage=active`；
- `experimental_active`：允许先行实验，但严格审核尚未闭合；对应当前
  `strict_stage=curated`。

因此本文不会把两者统称为“14 个 active”。

| ID | 形式化边界 | 实验角色 | 机器接受意味着 | 不意味着 |
|---|---|---|---|---|
| `erdos-307` | 固定 Lean 陈述 + 有限素数证书 | `experimental_active` | 两个有限素数集满足精确倒数等式，正向解决存在性 | bounded search 失败证明无解；Lean 已闭合 |
| `erdos-835` | 固定 Lean 陈述 + `k=10` 完整着色表 | `experimental_active` | `k=10` 给出全题所需存在见证 | 排除 `k=10` 解决所有 `k` |
| `erdos-64` | 固定 Lean 陈述 + 至多 64 点反例 | `audited_active` | 接受的有限图反驳全局猜想 | 搜不到反例证明猜想为真 |
| `erdos-23` | 固定 Lean 陈述 + 奇圈打包证书 | `experimental_active` | 三角形自由图需删超过 `n²` 条边，反驳全题 | 该证书形态覆盖所有可能反例 |
| `erdos-7` | 固定 Lean 陈述 + LCM 覆盖证书 | `experimental_active` | 得到互异奇模数覆盖系，正向解决存在性 | 当前 LCM 上限内失败证明无解 |
| `ramsey-r55` | 固定 Lean 陈述 + 43 点图 | `experimental_active` | 推进到 `R(5,5)≥44` | 确定 `R(5,5)` 的精确值 |
| `frontier-stretched-lr` | 精确 executable spec | `audited_active` | 冻结分拆范围内存在负系数反例 | 任意放宽边界后的结果自动有效 |
| `frontier-ramsey-book` | 精确 executable spec | `experimental_active` | 显式覆盖 `2≤n≤100` 的 99 个有限实例 | 已给出对所有 `n` 的统一算法 |
| `frontier-small-diophantine` | 精确 executable spec | `experimental_active` | 第一条未报告解决方程有 3 个不同的大 `x` 解 | 已证明无穷多解或解决其余八题 |
| `aim-60-first-prime` | 精确 executable spec | `experimental_active` | 完整认证一个 `x0≥1455091` 的实例 | 已确认世界纪录或全局最优；其 open-status gate 仍失败 |
| `cage-cubic-g13-record` | 精确 executable spec | `experimental_active` | 产生小于 272 点的三正则 girth-13 图 | 已确定精确 cage 数；必然仍是最新纪录 |
| `degree-diameter-3-9-record` | 精确 executable spec | `audited_active` | 产生超过 600 点、度至多 3、直径至多 9 的图 | 证明全局最优 |
| `srg-69-20-7-5` | 精确 executable spec | `experimental_active` | 正向解决该 SRG 参数的存在性 | 子类无解可升级为全局不存在 |
| `costas-order-32` | 精确 executable spec | `experimental_active` | 得到 32 阶 Costas array | 未刷新文献时即可声称新颖 |

组合的机器源是 [`data/experimental-portfolio.json`](../data/experimental-portfolio.json)。
其中 6 题的原命题具有固定 proof-assistant statement，8 题只有 executable spec；
两者均有有限候选 verifier，但前 6 题的最终 Lean proof closure 仍是独立阶段。

运行入口：

```bash
python scripts/verify_candidate.py --list
python scripts/verify_candidate.py <problem-id> <candidate.json>
```

退出码 0 表示候选在冻结边界内被接受，1 表示候选被数学/格式条件拒绝，2 表示
资源、完整性或调用失败。只有 3 个 `audited_active` 目标已经具备独立审核、红队、
基线和预算 receipts；其余实验结果必须先走这些步骤，才能进入
`data/active-portfolio.json`。

AIM #60 的 v2 门槛来自本轮公开检索中未发现更强同形实例的结果，以及公开页面上
`a=26060579, x0=1455090` 的报告。它足以定义一次先行实验，不足以证明 1455090
是当前纪录；不可省略提交前复查与独立证书重建。旧 v1 继续保留作 616980 回归。
