# Build-Grade-Loop（构建-评审-循环）

> 两个 Agent 自动循环：构建→评审→改进，直到分数达标。

> **⚠️ 平台要求：** 本 skill 依赖 Agent 平台的**子代理派发能力**（如 Hermes Agent 的 `delegate_task`）。不支持子代理的平台无法直接使用。详见[依赖](#依赖)。

## 为什么需要 AI

这个功能**没有 AI 根本做不到**——不是把传统工具套个 AI 壳。

传统工具能做到的：
- ✅ 自动运行测试脚本
- ✅ 记录分数和历史
- ✅ 检测文件是否存在

只有 AI 才能做到的：
- 🔮 **理解需求，从零构建项目**：给一句话描述，Agent 写出完整的代码、文档、测试
- 🔮 **跨维度评审质量**：不是跑 lint，是读代码、读文档、判断设计是否合理、测试是否充分
- 🔮 **理解扣分原因并针对性修复**：不是机械替换，是读懂"句子计数算法对连续标点处理不佳"然后改正则
- 🔮 **在没有明确规则的情况下做判断**：评分标准是"SKILL.md 质量 15 分"，具体怎么扣分靠 AI 理解

**本质区别：** 传统自动化是"按规则执行"，这个 skill 是"理解→判断→创造→改进"。每一步都依赖 AI 的语义理解能力。

## 这是什么？

一个 Hermes Agent skill，让 Agent A（构建者）和 Agent B（评审者）自动循环工作：

```
你："帮我把这个项目迭代到 90 分"
  ↓
Agent A 构建项目 → Agent B 评审打分 → 65分
  ↓（自动继续，不等你确认）
Agent A 改进 → Agent B 再评 → 80分
  ↓（自动继续）
Agent A 改进 → Agent B 终评 → 92分 ✅ 达标，结束
```

全程自动，你只需要开头说一句话。

## 功能

- **自动循环**：构建→评审→改进→再评审，直到达标或用完轮次
- **7 维度评分**：SKILL.md、脚本、参考文件、测试数据、测试记录、迭代记录、README
- **平台期检测**：分数连续不升时自动切换策略
- **状态持久化**：分数历史和评审反馈保存在磁盘，跨轮次传递
- **人类可介入**：每轮报告分数，平台期时暂停询问

## 使用方式

### 从零构建 + 迭代（完整能力）

```
帮我用 build-grade-loop 从零构建一个文本统计 skill，目标 90 分
项目路径：C:/Users/st/Desktop/text-stats/
功能：分析文本的字数、句数、段落数、平均句长
```

→ Agent A 根据需求从零构建项目 → Agent B 评审打分 → 自动循环改进

### 对已有项目迭代（部分能力）

```
帮我用 build-grade-loop 把 C:/Users/st/Desktop/my-project 迭代到 90 分
```

→ 跳过构建，直接进入评审→改进循环

### 自定义参数

```
用 build-grade-loop 迭代这个项目：
- 项目路径：D:/projects/skill-test/
- 目标分数：85
- 最大轮次：3
- 评分标准：代码质量 40分、文档 30分、测试 30分
```

### 推荐配置

| 场景 | target | max_rounds | 说明 |
|------|--------|------------|------|
| 快速迭代 | 85 | 3 | 3 轮能到 85 就很好了 |
| 标准迭代 | 90 | 5 | 默认配置，性价比最高 |
| 深度迭代 | 95 | 8 | 高分段每轮提升很慢 |

> ⚠️ target > 95 可能无法收敛。建议 90-95。

## 项目结构

```
Build-Grade-Loop/
├── skill/                              # Skill 文件
│   ├── SKILL.md                        # 技能定义（含 frontmatter + 工作流）
│   ├── scripts/
│   │   └── state_manager.py            # 状态管理工具（init/record/status/feedback/history）
│   └── references/
│       ├── implementer-prompts.md      # Agent A prompt 模板（首轮/改进轮/聚焦轮）
│       ├── reviewer-prompts.md         # Agent B prompt 模板（标准评审/验证修复）
│       ├── scoring-rubric.md           # 7 维度评分细则（100 分制）
│       ├── feedback-format.md          # feedback.md 文件格式规范
│       ├── plateau-strategies.md       # 平台期破局指南
│       ├── scoring-patterns.md         # 评分模式参考
│       └── usage-guide.md              # 详细使用指南
├── data/                               # 测试数据（e2e 测试用）
│   ├── sample1.txt                     # 多段落文本
│   ├── sample2.txt                     # 单句文本
│   ├── empty.txt                       # 空文件
│   ├── unicode.txt                     # 中文 + emoji
│   └── special_chars.txt              # 连续标点边界
├── tests/                              # 测试记录
│   ├── test_state_manager.py           # 脚本单元测试（26 用例，91 断言）
│   ├── test_record.md                  # 脚本测试记录
│   └── e2e_test_report.md             # 端到端测试报告
├── iteration/                          # 迭代记录
│   └── iteration_log.md               # 五步迭代法记录（2 轮迭代）
└── README.md                           # 本文件
```

## 工作原理

### 架构

```
主 Agent（Orchestrator，唯一持久会话）
  │
  ├── 每轮 delegate_task(Agent A) → 构建/改进 → 返回 → Agent A 消亡
  ├── 每轮 delegate_task(Agent B) → 评审打分 → 返回 → Agent B 消亡
  │
  └── 共享记忆：.iteration-state/feedback.md（Agent A 的改进依据）
```

Agent A 和 Agent B 都是**临时工**——每轮新建，用完即弃，没有记忆。`feedback.md` 是它们之间的共享记忆。

### 状态管理

```bash
python state_manager.py init --project /path --target 90 --max-rounds 5
python state_manager.py status --project /path          # 查看进度
python state_manager.py record --project /path --score 85  # 记录分数
python state_manager.py feedback --project /path --append "..."  # 追加反馈
python state_manager.py history --project /path          # JSON 输出
```

### 关键设计决策

1. **报告 ≠ 结束**：报告分数后自动继续下一轮，不等用户确认
2. **路径必须绝对**：Windows 上禁止 `/tmp/`、`~/`，用 `C:/Users/...` 
3. **Agent A 只修扣分项**：不做额外重构，避免引入新问题
4. **Agent B 必须执行验证**：不能只读代码打分，要运行脚本

### 为什么用两个 Agent 而不是一个？

| | 两个 Agent（A 实现 + B 评审） | 一个 Agent 两种角色 |
|---|---|---|
| 评审客观性 | ✅ A 不知道 B 会怎么评，B 不知道 A 的意图 | ⚠️ 自己评自己，容易放水 |
| 上下文干扰 | ✅ 各自只关注自己的任务 | ⚠️ 实现代码和评审标准混在同一个上下文 |
| 角色一致性 | ✅ A 始终是实现者，B 始终是评审者 | ⚠️ 角色切换时可能混淆 |
| 成本 | ⚠️ 每轮 2 次 delegate_task | ✅ 每轮 1 次 |

**核心原因：人不会让作者自己给自己的论文打分。** 评审的客观性来自视角分离。一个 Agent 即使用 system prompt 切换角色，它仍然"记得"自己刚写了什么代码，很难做到真正的客观评分。

## 迭代历史

| 迭代 | 痛点 | 修复 | 验证 |
|------|------|------|------|
| #1 | Windows `/tmp/` 路径歧义导致循环断裂 | SKILL.md 加 Path Rules + 文件验证步骤 | ✅ 用确定路径后循环跑通 |
| #2 | Orchestrator 报告完分数就停止 | Step 3 拆为 4 步 + "报告≠结束"硬规则 | ✅ 3 轮连续执行未停顿 |

详细记录见 `iteration/iteration_log.md`。

## 测试结果

### 脚本单元测试

```
📊 91 passed / 0 failed / 26 个测试用例
🎉 ALL TESTS PASSED!
```

### 端到端测试（迭代 2 修复后）

```
Round 1: 65分 → Round 2: 80分 → Round 3: 99分 ✅ 达标
全程未停顿，自动循环至结束。
```

详细报告见 `tests/e2e_test_report.md`。

## 成本估算

| 轮次 | Agent A tokens | Agent B tokens | 合计 |
|------|---------------|---------------|------|
| 1 轮 | ~5,000 | ~10,000 | ~15,000 |
| 3 轮 | ~15,000 | ~30,000 | ~45,000 |
| 5 轮 | ~25,000 | ~50,000 | ~75,000 |

## 依赖

### 必须：支持子代理（Sub-Agent）的 Agent 平台

本 skill 的核心机制是**派发子代理**——主 Agent 将"构建"和"评审"分别委托给两个独立的子 Agent 执行。这要求 Agent 平台具备以下能力：

1. **子代理派发**：主 Agent 能创建隔离的子会话执行任务，子会话完成后返回结果
2. **工具调用**：子 Agent 能读写文件、运行脚本
3. **上下文传递**：主 Agent 能将需求和反馈作为参数传给子 Agent

**已验证的平台：**

| 平台 | 子代理能力 | 状态 |
|------|-----------|------|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | `delegate_task` 工具 | ✅ 已测试 |

**理论兼容但未测试的平台：**

| 平台 | 对应能力 |
|------|----------|
| CrewAI | Crew + Agent 分工 |
| AutoGen | Multi-agent conversation |
| LangGraph | Subgraph delegation |
| OpenAI Swarm | Agent handoff |

> ⚠️ 如果你的 Agent 平台**不支持子代理**，本 skill 的当前实现无法直接使用。但核心概念（构建→评审→循环）可以通过**单 Agent 角色切换**实现——同一个 Agent 先扮演实现者，再扮演评审者。效果会有折扣（上下文污染），但不需要子代理能力。

### 其他依赖

- **skill-project-review**：Agent B 使用的评审方法论 skill（7 维度 rubric）
- **Python 3.9+**：`state_manager.py` 使用了 `list[str]` 类型注解
- **Python stdlib**：脚本仅使用 `json`、`argparse`、`pathlib`、`subprocess`，无第三方依赖
