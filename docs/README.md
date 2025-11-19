# CherryQuant 文档中心

欢迎来到 CherryQuant 项目文档中心！本目录包含项目的所有文档，按主题分类组织。

## 📚 文档导航

### 🎓 教学资源（学生必读）

#### 课程模块
完整的课程教学材料，涵盖从基础到高级的所有主题。

- 📖 **[Module 0: 前置知识与环境搭建](course/00_Prerequisites.md)** - 开发环境配置和基础知识
- 📖 **[Module 1: 系统架构设计](course/01_System_Architecture.md)** - 六边形架构和系统设计
- 📖 **[Module 2: 数据管道](course/02_Data_Pipeline.md)** - 数据获取、处理和存储
- 📖 **[Module 3: AI 决策引擎](course/03_AI_Decision_Engine.md)** - LLM 集成和提示工程
- 📖 **[Module 4: 交易执行](course/04_Trading_Execution.md)** - 订单管理和风险控制
- 📖 **[Module 5: 依赖注入实战](course/05_Dependency_Injection.md)** - DI 模式和 Composition Root
- 📖 **[Module 7: Python 代码规范](course/07_Python_Best_Practices.md)** - 类型提示、代码格式化、异步编程

#### 实验指导
动手实践，巩固理论知识。

- 🧪 **[实验总览](labs/README.md)** - 实验规范、评分标准、提交要求
- 🧪 **[Lab 01: 环境搭建与首次运行](labs/lab01_environment_setup.md)** (2h, ⭐入门)
- 🧪 **[Lab 02: 追踪数据流](labs/lab02_data_flow.md)** (3h, ⭐⭐初级)
- 🧪 **[Lab 03: 提示词工程实验](labs/lab03_prompt_engineering.md)** (4h, ⭐⭐⭐中级)

---

### 📘 操作指南（实用手册）

快速上手和日常操作的指南。

- 🚀 **[快速开始](guides/quick-start.md)** - 5 分钟快速运行项目
- 💾 **[数据下载指南](guides/data-download.md)** - 获取历史数据和配置数据源
- 📝 **[日志使用指南](guides/logging.md)** - Structlog 配置和日志分析
- 🎯 **[WARP 功能](guides/warp-features.md)** - 项目特色功能说明
- 🔧 **[配置指南](guides/configuration/)** - 环境变量和系统配置
  - [SimNow 模拟环境配置](guides/configuration/simnow_setup.md)

---

### 📖 参考文档（深入学习）

详细的技术参考和高级主题。

#### 架构与设计
- 🏗️ **[架构总览](reference/architecture.md)** - 系统架构详细说明
- 🏗️ **[架构设计文档](reference/architecture-design.md)** - 设计决策和模式
- 🔄 **[数据管道详解](reference/data-pipeline.md)** - 数据流和处理机制
- 🔤 **[合约代码标准化](reference/symbol-standardization.md)** - 期货合约命名规范

#### VNPy 集成
- 📊 **[VNPy Recorder](reference/vnpy-recorder.md)** - 实时数据录制器

#### API 参考
- 🔌 **[API 使用说明](reference/api/USAGE.md)** - API 接口总览
- 🤖 **[AI 决策 API](reference/api/ai_decision_api.md)** - AI 决策引擎接口

#### 测试相关
- ✅ **[测试用例](reference/testing/test_cases.md)** - 测试场景和用例

#### 高级主题（可选）
- 🚀 **[生产环境部署](reference/advanced/PRODUCTION_DEPLOYMENT.md)** - 生产部署指南
- 📊 **[QuantBox 集成](reference/advanced/QUANTBOX_INTEGRATION.md)** - 高性能数据源集成
- ⚠️ **[风险配置详解](reference/advanced/RISK_CONFIG_GUIDE.md)** - 风险参数配置
- 🔧 **[故障排查](reference/advanced/TROUBLESHOOTING.md)** - 常见问题解决
- 📖 **[用户手册](reference/advanced/USER_GUIDE.md)** - 完整用户使用手册

---

### 📝 架构决策记录（ADR）

重要的技术决策及其背景。

- 📋 **[ADR 总览](adr/README.md)** - 架构决策记录索引
- 📋 **[ADR-0001: 使用 MongoDB](adr/0001-use-mongodb.md)** - 为什么选择 MongoDB 而非 PostgreSQL
- 📋 **[ADR-0002: 依赖注入](adr/0002-dependency-injection.md)** - 依赖注入模式的选择
- 📋 **[ADR-0003: 提示工程而非微调](adr/0003-prompt-engineering-ai.md)** - AI 策略设计决策

---

### 📊 项目报告（进展记录）

项目验证、测试和里程碑报告。

- ✅ **[项目验证报告](reports/verification.md)** - 项目功能验证
- 🧪 **[测试报告](reports/testing.md)** - 测试结果总结
- 📈 **[测试覆盖率](reports/testing-coverage.md)** - 代码覆盖率分析

---

### 🗄️ 历史归档

历史文档，仅供参考。

- 📦 **[归档文档](archive/)** - 已完成的迁移、交付等历史文档

---

## 🗺️ 学习路径推荐

### 初学者（Week 1-2）
1. 📖 根目录 `README.md` - 了解项目定位
2. 📖 根目录 `LEARNING_PATH.md` - 查看 10 周学习路径
3. 📖 `course/00_Prerequisites.md` - 配置环境
4. 🧪 `labs/lab01_environment_setup.md` - 完成第一个实验
5. 🚀 `guides/quick-start.md` - 快速运行项目

### 进阶学习（Week 3-5）
1. 📖 `course/01_System_Architecture.md` - 理解系统架构
2. 📖 `course/02_Data_Pipeline.md` - 学习数据管道
3. 🧪 `labs/lab02_data_flow.md` - 追踪数据流
4. 📖 `course/03_AI_Decision_Engine.md` - AI 决策引擎
5. 🧪 `labs/lab03_prompt_engineering.md` - 提示词工程实验

### 高级主题（Week 6-9）
1. 📖 `course/04_Trading_Execution.md` - 交易执行
2. 📖 `course/05_Dependency_Injection.md` - 依赖注入实战
3. 📖 `course/07_Python_Best_Practices.md` - 代码规范
4. 📋 查阅 `adr/` 下的架构决策记录
5. 📖 `reference/` 下的详细技术参考

### 项目实践（Week 10）
1. 📖 `reference/architecture.md` - 深入理解架构
2. 📖 `reference/advanced/` - 学习生产级特性
3. 🚀 完成毕业项目

---

## 📁 目录结构

```
docs/
├── README.md                 # 本文件 - 文档导航
│
├── course/                   # 课程模块（按周组织）
│   ├── 00_Prerequisites.md
│   ├── 01_System_Architecture.md
│   ├── 02_Data_Pipeline.md
│   ├── 03_AI_Decision_Engine.md
│   ├── 04_Trading_Execution.md
│   ├── 05_Dependency_Injection.md
│   └── 07_Python_Best_Practices.md
│
├── labs/                     # 实验指导（配合课程）
│   ├── README.md
│   ├── lab01_environment_setup.md
│   ├── lab02_data_flow.md
│   └── lab03_prompt_engineering.md
│
├── guides/                   # 操作指南（实用手册）
│   ├── quick-start.md
│   ├── data-download.md
│   ├── logging.md
│   ├── warp-features.md
│   └── configuration/
│       └── simnow_setup.md
│
├── reference/                # 技术参考（深入学习）
│   ├── architecture.md
│   ├── architecture-design.md
│   ├── data-pipeline.md
│   ├── symbol-standardization.md
│   ├── vnpy-recorder.md
│   ├── api/
│   │   ├── USAGE.md
│   │   └── ai_decision_api.md
│   ├── testing/
│   │   └── test_cases.md
│   └── advanced/             # 生产级特性（可选）
│       ├── PRODUCTION_DEPLOYMENT.md
│       ├── QUANTBOX_INTEGRATION.md
│       ├── RISK_CONFIG_GUIDE.md
│       ├── TROUBLESHOOTING.md
│       └── USER_GUIDE.md
│
├── adr/                      # 架构决策记录
│   ├── README.md
│   ├── 0000-template.md
│   ├── 0001-use-mongodb.md
│   ├── 0002-dependency-injection.md
│   └── 0003-prompt-engineering-ai.md
│
├── reports/                  # 项目报告
│   ├── verification.md
│   ├── testing.md
│   └── testing-coverage.md
│
└── archive/                  # 历史归档
    ├── DATABASE_MIGRATION_PLAN.md
    ├── DELIVERY_CHECKLIST.md
    ├── MIGRATION_GUIDE.md
    └── MONGODB_MIGRATION_COMPLETE.md
```

---

## 🔍 快速查找

### 按需求查找

**我想...**
- ❓ 开始学习这个项目 → `../README.md` + `../LEARNING_PATH.md`
- ❓ 配置开发环境 → `course/00_Prerequisites.md` + `labs/lab01_environment_setup.md`
- ❓ 快速运行项目 → `guides/quick-start.md`
- ❓ 理解系统架构 → `course/01_System_Architecture.md` + `reference/architecture.md`
- ❓ 获取历史数据 → `guides/data-download.md`
- ❓ 使用 AI 决策 → `course/03_AI_Decision_Engine.md` + `reference/api/ai_decision_api.md`
- ❓ 了解为什么这样设计 → `adr/` 目录
- ❓ 解决问题 → `reference/advanced/TROUBLESHOOTING.md`
- ❓ 部署到生产环境 → `reference/advanced/PRODUCTION_DEPLOYMENT.md`

### 按角色查找

**学生**
- 📚 必读: `course/` + `labs/`
- 📖 参考: `guides/` + `reference/`

**教师**
- 📚 课程设计: `course/` + `labs/README.md`
- 📊 评估标准: 每个 lab 的评分部分

**开发者**
- 🏗️ 架构理解: `reference/architecture*.md` + `adr/`
- 🔌 API 使用: `reference/api/`
- 🧪 测试: `reference/testing/`

**运维人员**
- 🚀 部署: `reference/advanced/PRODUCTION_DEPLOYMENT.md`
- 🔧 配置: `guides/configuration/` + `reference/advanced/RISK_CONFIG_GUIDE.md`
- 🔍 故障排查: `reference/advanced/TROUBLESHOOTING.md`

---

## 📞 获取帮助

- **文档问题**: 检查本 README 或相关子目录的 README
- **代码问题**: 参考 `reference/` 和 `adr/`
- **实验问题**: 查看对应 lab 的 FAQ 部分
- **环境问题**: `reference/advanced/TROUBLESHOOTING.md`

---

## 🤝 文档贡献

如果你发现文档有误或需要补充，欢迎提交 Issue 或 Pull Request！

**文档规范**:
- 使用 Markdown 格式
- 中文文档优先
- 包含代码示例
- 添加目录和锚点链接
- 遵循现有的目录结构

---

**最后更新**: 2024-11-19
**维护者**: CherryQuant Team
