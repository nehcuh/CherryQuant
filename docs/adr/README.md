# 架构决策记录（Architecture Decision Records - ADR）

## 概述

本目录包含 CherryQuant 项目的架构决策记录（ADR）。ADR 记录了项目中的重要架构和技术决策，帮助团队理解"为什么"做出特定选择。

## 什么是 ADR？

架构决策记录是一种轻量级文档，用于记录项目中的重要架构决策。每个 ADR 描述：
- 面临的问题和背景
- 考虑的解决方案
- 最终的决策
- 决策的后果和权衡

## ADR 的价值

1. **知识传承**：新团队成员可以快速了解架构演进历史
2. **决策追溯**：理解当时为什么做出某个决策
3. **避免重复讨论**：已经讨论过的问题不需要重新讨论
4. **提高透明度**：让技术决策过程更加透明

## 何时编写 ADR？

当你面临以下情况时，应该编写 ADR：
- ✅ 选择核心技术栈（数据库、框架、语言等）
- ✅ 重要的架构模式决策（微服务 vs 单体、事件驱动等）
- ✅ 显著影响系统性能、可维护性或成本的决策
- ✅ 有多个可行方案，需要权衡利弊的决策
- ✅ 可能在未来被质疑或重新考虑的决策

不需要为以下情况编写 ADR：
- ❌ 日常的代码实现细节
- ❌ 显而易见的选择（如使用 Python 的标准库）
- ❌ 临时性的实验或原型

## ADR 目录结构

```
docs/adr/
├── README.md                    # 本文件
├── 0000-template.md             # ADR 模板
├── 0001-use-mongodb.md          # 示例：选择 MongoDB
├── 0002-dependency-injection.md # 示例：依赖注入模式
├── 0003-prompt-engineering.md   # 示例：AI 提示工程
└── ...
```

## ADR 命名规范

```
<序号>-<简短描述>.md

示例：
- 0001-use-mongodb.md
- 0002-adopt-hexagonal-architecture.md
- 0003-integrate-quantbox.md
```

- **序号**：4 位数字，从 0001 开始递增
- **简短描述**：使用 kebab-case，简洁描述决策内容
- **语言**：英文描述，内容可用中文

## 如何编写 ADR

### 1. 复制模板

```bash
cp docs/adr/0000-template.md docs/adr/XXXX-your-decision.md
```

### 2. 填写内容

按照模板的各个部分填写：
- **状态**：Proposed（提议）→ Accepted（接受）→ Deprecated（废弃）或 Superseded（被替代）
- **背景**：描述问题和上下文
- **决策**：明确说明选择的方案
- **后果**：列出正面和负面影响

### 3. 评审和批准

- 提交 Pull Request
- 团队成员评审
- 合并后状态改为 "Accepted"

## ADR 状态

- **Proposed（提议中）**：ADR 已创建，等待评审和批准
- **Accepted（已接受）**：决策已被批准和实施
- **Deprecated（已废弃）**：决策不再推荐使用，但系统中可能still存在
- **Superseded by ADR-XXXX**：被新的 ADR 替代

## ADR 列表

| 序号 | 标题 | 状态 | 日期 |
|------|------|------|------|
| [0000](0000-template.md) | ADR 模板 | Template | - |
| [0001](0001-use-mongodb.md) | 使用 MongoDB 作为主数据库 | Accepted | 2025-10-15 |
| [0002](0002-dependency-injection.md) | 采用依赖注入模式 | Accepted | 2025-10-18 |
| [0003](0003-prompt-engineering-ai.md) | AI 策略：提示工程而非微调 | Accepted | 2025-09-01 |
| [0004](0004-integrate-quantbox.md) | 集成 QuantBox 数据管理 | Accepted | 2025-10-20 |

## 参考资源

- [ADR GitHub Organization](https://adr.github.io/)
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR Tools](https://github.com/npryce/adr-tools)
- [When to Use ADRs](https://github.com/joelparkerhenderson/architecture-decision-record)
