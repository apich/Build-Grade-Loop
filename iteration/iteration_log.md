# Iteration Log — implement-review-loop

## 迭代 1：Windows 路径歧义导致循环断裂

### Step 1: 描述痛点

端到端测试中，用 `/tmp/skill-test-project/` 作为项目路径。Agent A 构建完成后声称"7/7 测试通过"，但 Agent B 评审时发现目录是空的（0 个文件）。

排查发现：Agent A 把文件写到了 `C:\tmp\skill-test-project\`，而 `state_manager.py init` 把状态文件创建在了 `C:\Users\st\AppData\Local\Temp\skill-test-project\`（MSYS `/tmp/` 的真实映射）。两个不同的物理路径，导致 Agent B 在错误的路径下找不到任何文件。

### Step 2: 量化影响

- 影响范围：Windows + MSYS/Git Bash 环境下所有使用 `/tmp/` 或 `~/` 的场景
- 严重程度：循环完全断裂——Agent A 写的文件 Agent B 看不到，state_manager 记录的路径和实际文件不一致
- 测试表现：Round 1 评审 Agent B 给出 0/100 分（不是因为项目质量差，而是因为找不到文件）

### Step 3: 假设原因

Windows MSYS 环境下 `/tmp/` 存在路径映射歧义：
- MSYS bash 的 `/tmp/` → `C:\Users\st\AppData\Local\Temp\`（通过 `cygpath -w /tmp` 验证）
- Agent A（delegate_task 子进程）可能用 Python 的 `os.path` 解析为 `C:\tmp\`
- 两层路径解析机制不同，同一字符串 `/tmp/` 在不同上下文指向不同物理位置

### Step 4: 实现方案

在 SKILL.md 的 Prerequisites 中增加 **Path Rules** 段落：

```markdown
### ⚠️ Path Rules (CRITICAL — e2e tested, 2026-07-12)

必须使用确定的绝对路径。
- ✅ 正确：C:/Users/st/Desktop/my-project/
- ❌ 错误：/tmp/my-project/（Windows 路径歧义）
- ❌ 错误：~/my-project/（~ 在不同上下文展开不同）

Orchestrator 在 Step 0 中应验证路径可用性：terminal: ls <project_path>
```

同时在 Step 1 增加文件验证步骤：Agent A 返回后，orchestrator 必须用 `search_files` 验证文件确实存在于预期路径。

### Step 5: 评估效果

修复后用 `C:/Users/st/Desktop/skill-test-project/` 重新测试：
- ✅ Agent A 创建的 9 个文件全部在正确路径
- ✅ Agent B 成功读取所有文件并评审
- ✅ Round 1 评审得分 59/100（正常打分，不再是 0 分）
- ✅ Round 2 Agent A 改进后 Agent B 再评审得分 88/100
- ✅ 整个 Round 1 → Round 2 循环跑通

**结论：路径问题已修复。**

---

## 迭代 2：Orchestrator 报告完分数就停止，没有继续下一轮

### Step 1: 描述痛点

Round 1 结束后，orchestrator（即主 Agent）执行了：
1. `state_manager.py record --score 59` ✅
2. `state_manager.py feedback --append "评审报告"` ✅
3. 向用户报告"得分 59/100，发现 3 个 bug" ✅
4. **然后就停了，没有继续 Round 2** ❌

用户需要手动催促"怎么只跑了一轮"才继续。

### Step 2: 量化影响

- 影响范围：所有使用该 skill 的场景（不是偶发，是结构性问题）
- 严重程度：循环只跑了 1 轮就中断，完全失去了"自动迭代"的意义
- 测试表现：Round 1 得 59 分后停止，用户手动催促后才跑 Round 2 得 88 分。如果没有用户介入，永远停在 59 分

### Step 3: 假设原因

SKILL.md 的 Step 3（原名 "Record and Decide"）写的是：

> Agent 根据 `status` 输出自主判断：
> - `TARGET REACHED` → 结束
> - `PLATEAU` → 聚焦策略
> - 其他 → 将报告追加到 feedback.md，回到 Step 1

问题在于：
1. "自主判断"太模糊——Agent 自然倾向于在汇报后等待用户指令
2. Step 3 的流程是"记录 → 判断"，没有显式包含"报告 → 继续"
3. 没有任何地方明确说"报告 ≠ 结束"——Agent 把"向用户报告分数"当成了任务终点
4. LLM 的对话模式是"说完等回复"，而循环需要"说完继续做"——这是反直觉的行为

### Step 4: 实现方案

1. **Step 3 重写**：从 `Record and Decide` 改为 `Record, Report, and Continue`，拆为 4 个显式子步骤：
   - 3a. 记录分数（state_manager.py record）
   - 3b. 追加反馈（state_manager.py feedback）
   - 3c. 向用户报告（一行简短消息）
   - 3d. 判断下一步（自动执行，不等用户）

2. **新增 🔴 关键规则**：
   > 报告 ≠ 结束。只有达标/超轮次/平台期才停止，其他情况报告完立即继续。不要等。不要问。直接做。

3. **新增 Pitfall 0**：记录此 bug 的现象、根因、错误/正确行为对比、验证清单

4. **更新执行流程图**：第 7 步改为"立即回到第 1 步（不等用户回复）"

5. **更新验证清单**：增加"报告后是否立即继续"检查项

### Step 5: 评估效果（2026-07-12 验证）

修复后的 SKILL.md 变化：
- Step 3 从 1 段模糊描述变为 4 个显式子步骤（3a/3b/3c/3d）
- 新增"报告 ≠ 结束"的硬规则，用 ❌/✅ 对比
- 新增 Pitfall 0，包含完整的 bug 记录和验证清单
- 执行流程图第 7 步明确写"立即回到第 1 步（不等用户回复）"
- 验证清单新增 1 项："报告分数后，如果未达标且未超轮次，立即开始下一轮"

**验证结果：** 用修复后的 skill 重新跑了完整 3 轮端到端测试。

| 轮次 | 动作 | 是否停顿 |
|------|------|----------|
| Round 1 | Agent A 构建 → Agent B 评审 (65分) → record+feedback+报告 → **立即启动 Round 2** | ❌ 未停顿 |
| Round 2 | Agent A 改进 → Agent B 再评审 (80分) → record+feedback+报告 → **立即启动 Round 3** | ❌ 未停顿 |
| Round 3 | Agent A 改进 → Agent B 最终评审 (99分) → record+feedback+报告 → **Finalize** | ❌ 未停顿（达标自动结束） |

分数趋势：65 → 80 → 99（target=90，第 3 轮达标）

**结论：迭代 2 修复已验证。Orchestrator 报告分数后自动继续下一轮，未等用户确认，未中途停止。**
