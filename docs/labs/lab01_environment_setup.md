# Lab 01: 环境搭建与首次运行

## 实验信息

- **难度**: ⭐ 入门
- **预计时间**: 2 小时
- **相关模块**: Module 0: 前置知识与环境搭建
- **截止日期**: Week 1 结束

## 学习目标

完成本实验后，你将能够：

1. ✅ 在本地成功配置 CherryQuant 开发环境
2. ✅ 理解项目的目录结构和核心组件
3. ✅ 运行第一个 CherryQuant 示例程序
4. ✅ 使用基本的开发工具（uv, Docker, Git）
5. ✅ 进行环境问题的诊断和排错

## 实验前准备

### 必备知识

- [ ] 基本的命令行操作（cd, ls, mkdir 等）
- [ ] 了解环境变量的概念
- [ ] 基础的 Python 知识

### 需要安装的软件

- [ ] Python 3.12+
- [ ] uv 包管理器
- [ ] Docker Desktop
- [ ] Git
- [ ] 代码编辑器（VS Code 推荐）

### 参考资料

- 📖 `docs/course/00_Prerequisites.md`
- 📖 `README.md`
- 📖 `LEARNING_PATH.md`

## 实验任务

### 任务 1: 安装基础软件 (30 分钟)

#### 1.1 安装 Python 3.12

**macOS**:
```bash
# 使用 Homebrew
brew install python@3.12

# 验证安装
python3.12 --version
```

**Ubuntu/Debian**:
```bash
# 添加 PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# 安装 Python 3.12
sudo apt install python3.12 python3.12-venv python3.12-dev

# 验证安装
python3.12 --version
```

**✅ 检查点**: 确认输出 `Python 3.12.x`

#### 1.2 安装 uv 包管理器

```bash
# 一键安装
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证安装
uv --version
```

**✅ 检查点**: 确认输出 `uv 0.x.x`

**如果遇到 "uv: command not found"**:
```bash
# 添加到 PATH
export PATH="$HOME/.cargo/bin:$PATH"

# 永久添加（macOS/Linux）
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

#### 1.3 安装 Docker Desktop

**macOS/Windows**:
- 访问 https://www.docker.com/products/docker-desktop/
- 下载并安装 Docker Desktop
- 启动 Docker Desktop

**Linux**:
```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 添加当前用户到 docker 组
sudo usermod -aG docker $USER
newgrp docker

# 安装 Docker Compose
sudo apt install docker-compose-plugin
```

**验证安装**:
```bash
docker --version
docker compose version
```

**✅ 检查点**: 两个命令都能正确输出版本号

#### 1.4 安装 Git

```bash
# macOS
brew install git

# Ubuntu/Debian
sudo apt install git

# 验证
git --version
```

**配置 Git** (首次使用):
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

**✅ 检查点**: `git --version` 输出版本号

---

### 任务 2: 克隆项目并配置环境 (30 分钟)

#### 2.1 克隆 CherryQuant 项目

```bash
# 选择一个合适的目录
cd ~/Projects

# 克隆项目
git clone https://github.com/your-username/CherryQuant.git

# 进入项目目录
cd CherryQuant

# 查看项目结构
ls -la
```

**✅ 检查点**: 确认看到以下目录:
- `config/`
- `src/`
- `examples/`
- `docs/`
- `tests/`
- `pyproject.toml`
- `README.md`

#### 2.2 使用一键配置脚本（推荐）

```bash
# 运行学生环境配置脚本
bash scripts/teaching/student_setup.sh
```

**脚本会自动完成**:
- ✅ 检查 Python 版本
- ✅ 创建虚拟环境
- ✅ 安装所有依赖
- ✅ 创建 `.env` 配置文件
- ✅ 启动数据库服务

**如果脚本成功**, 跳到任务 3。

**如果脚本失败**, 继续手动配置↓

#### 2.3 手动配置（备选方案）

**创建虚拟环境并安装依赖**:
```bash
# uv 会自动创建虚拟环境
uv venv

# 激活虚拟环境（可选）
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
uv sync
```

**创建 .env 配置文件**:
```bash
# 从模板复制
cp .env.example .env

# 编辑配置文件
vim .env  # 或使用你喜欢的编辑器
```

**最小配置**（`.env` 文件内容）:
```bash
# 基础配置
LOG_LEVEL=INFO
DEBUG=true

# 数据库配置
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB_NAME=cherryquant_dev

REDIS_HOST=localhost
REDIS_PORT=6379

# 以下暂时可以留空
# TUSHARE_TOKEN=
# OPENAI_API_KEY=
```

**✅ 检查点**: `.env` 文件存在且包含必要配置

#### 2.4 启动数据库服务

```bash
# 启动 MongoDB 和 Redis
docker compose up -d mongodb redis

# 查看服务状态
docker compose ps

# 查看日志（确认启动成功）
docker compose logs mongodb
docker compose logs redis
```

**预期输出**:
```
NAME                IMAGE               STATUS
cherryquant-mongodb   mongo:5.0          Up
cherryquant-redis     redis:7.0          Up
```

**✅ 检查点**: 两个服务都显示 "Up" 状态

**常见问题**:

**问题 1**: "Cannot connect to the Docker daemon"
```bash
# 解决: 启动 Docker Desktop
# macOS: 打开 Docker Desktop 应用
# Linux: sudo systemctl start docker
```

**问题 2**: 端口被占用
```bash
# 查看占用端口的进程
lsof -i :27017  # MongoDB
lsof -i :6379   # Redis

# 修改 docker-compose.yml 中的端口映射，或停止占用进程
```

---

### 任务 3: 运行第一个示例程序 (20 分钟)

#### 3.1 运行 Hello CherryQuant

```bash
# 运行示例
uv run python examples/01_basics/hello_cherryquant.py
```

**预期输出**:
```
============================================================
🍒 欢迎使用 CherryQuant AI 量化交易教学项目！
============================================================

📋 项目基本信息:
  • 项目根目录: /Users/xxx/Projects/CherryQuant
  • 日志级别: INFO
  • 是否启用调试模式: True

🗄️  数据库配置:
  • MongoDB 数据库: cherryquant_dev
  • Redis 主机: localhost

📊 支持的期货品种 (共 X 个):
  • 黑色系: rb, hc, i, j, jm
  • 有色金属: cu, al, zn, pb, ni, sn
  • 能源化工: ru, bu, fu, lu, ...
  • 农产品: c, cs, a, m, y, p, ...

============================================================
✅ 示例运行成功！
============================================================

💡 下一步:
  1. 阅读 docs/course/01_System_Architecture.md 了解系统架构
  2. 运行 examples/02_data/ 下的数据获取示例
  3. 完成 Lab 01 实验任务
```

**✅ 检查点**: 程序成功运行并输出类似上述内容

**如果遇到错误**:

**错误 1**: `ModuleNotFoundError`
```bash
# 确保使用 uv run
uv run python examples/01_basics/hello_cherryquant.py

# 或者激活虚拟环境后运行
source .venv/bin/activate
python examples/01_basics/hello_cherryquant.py
```

**错误 2**: 配置文件错误
```bash
# 检查 .env 文件是否存在
ls -la .env

# 检查配置文件内容
cat .env
```

#### 3.2 截图保存结果

**要求**: 截取完整的终端输出，包括:
- 命令提示符（显示当前目录）
- 运行的命令
- 完整的输出结果

**保存位置**: 准备提交到实验报告中

---

### 任务 4: 环境验证 (20 分钟)

#### 4.1 运行环境验证脚本

```bash
uv run python scripts/teaching/verify_environment.py
```

**预期输出**:
```
============================================================
🔍 CherryQuant 环境验证
============================================================

📋 基础环境检查:
  ✅ Python 版本: Python 3.12.x
  ✅ uv 包管理器: uv 0.x.x
  ✅ .env 配置文件: /path/to/.env
  ✅ Python 依赖: 所有关键依赖已安装
  ✅ 项目目录结构: 所有必需目录存在

🗄️  数据库服务检查:
  ✅ MongoDB: localhost:27017
  ✅ Redis: localhost:6379

============================================================
📊 检查结果: 7/7 项通过 (100.0%)
============================================================

🎉 恭喜！环境配置完全正确！

💡 下一步:
  1. 运行示例: uv run python examples/01_basics/hello_cherryquant.py
  2. 学习 Module 1: docs/course/01_System_Architecture.md
  3. 完成 Lab 01 实验任务
```

**✅ 检查点**: 所有检查项都显示 ✅

**如果有检查项失败**:

根据错误提示修复问题，常见问题：

- **MongoDB/Redis 连接失败**: 确保 Docker 服务运行中
- **.env 文件不存在**: `cp .env.example .env`
- **Python 依赖缺失**: `uv sync`

#### 4.2 保存验证结果

```bash
# 将输出保存到文件
uv run python scripts/teaching/verify_environment.py > lab01_verification.txt
```

**✅ 检查点**: 生成 `lab01_verification.txt` 文件

---

### 任务 5: 理解项目结构 (30 分钟)

#### 5.1 探索项目目录

使用 `tree` 命令（或手动）探索项目结构:

```bash
# 安装 tree (如果没有)
# macOS: brew install tree
# Ubuntu: sudo apt install tree

# 查看项目结构（限制深度）
tree -L 2 -I '.venv|__pycache__|*.pyc'
```

#### 5.2 绘制思维导图

**要求**: 绘制项目目录结构的思维导图，包括:

**核心目录**:
- `config/` - 配置管理
- `src/cherryquant/` - 核心代码
- `examples/` - 示例代码
- `docs/` - 文档
- `tests/` - 测试代码

**关键文件**:
- `pyproject.toml` - 项目配置
- `.env` - 环境变量
- `README.md` - 项目说明

**可以使用**:
- 手绘（拍照）
- 在线工具: draw.io, MindMeister, XMind
- Markdown 图表

**示例结构** (Markdown 版本):

```
CherryQuant/
├── config/              配置管理
│   ├── settings/        设置模块
│   └── symbols.py       期货品种配置
│
├── src/cherryquant/     核心代码
│   ├── bootstrap/       依赖注入启动
│   ├── adapters/        适配器层
│   │   ├── data_adapter/     数据适配器
│   │   └── data_storage/     存储适配器
│   ├── ai/              AI 决策引擎
│   └── services/        业务服务
│
├── examples/            示例代码（分5个目录）
├── docs/                文档
│   ├── course/          课程模块
│   ├── labs/            实验指导
│   └── adr/             架构决策记录
│
├── tests/               测试代码
├── pyproject.toml       项目配置
└── .env                 环境变量
```

**✅ 检查点**: 完成思维导图绘制

#### 5.3 阅读关键文档

**必读**:
- [ ] `README.md` - 了解项目定位和快速开始
- [ ] `LEARNING_PATH.md` - 了解 10 周学习路径
- [ ] `examples/README.md` - 了解示例代码组织

**选读**:
- [ ] `docs/course/00_Prerequisites.md`
- [ ] `docs/adr/0003-prompt-engineering-ai.md`

**✅ 检查点**: 阅读完必读文档，记录关键要点

---

### 任务 6: 初识代码 (30 分钟)

#### 6.1 阅读第一个示例代码

打开并阅读 `examples/01_basics/hello_cherryquant.py`:

**阅读要点**:
1. 如何导入项目模块？
2. 如何加载配置？
3. 如何使用结构化日志？
4. 期货品种数据存储在哪里？

#### 6.2 修改并运行

**小任务**: 修改代码，添加一个新功能

```python
# 在 main() 函数末尾添加
print("\n🎓 学生信息:")
print(f"  • 姓名: 你的姓名")
print(f"  • 学号: 你的学号")
print(f"  • 班级: 你的班级")
```

**运行修改后的代码**:
```bash
uv run python examples/01_basics/hello_cherryquant.py
```

**✅ 检查点**: 代码成功运行并显示你添加的信息

---

## 实验提交

### 提交内容

1. **环境验证结果** (必须)
   - `lab01_verification.txt` 文件（或截图）

2. **示例运行截图** (必须)
   - `hello_cherryquant.py` 的完整运行输出

3. **项目结构思维导图** (必须)
   - 手绘照片或电子版图片

4. **修改后的代码** (必须)
   - `hello_cherryquant.py` 的修改版本

5. **实验报告** (必须)
   - 使用 `docs/labs/README.md` 中的模板
   - 至少 500 字的学习收获

### 提交方式

- 将所有文件打包为 `学号_姓名_Lab01.zip`
- 提交到课程平台或发送到指定邮箱

### 提交截止日期

- Week 1 结束前

---

## 评分标准 (10 分)

| 评分项 | 分值 | 要求 |
|--------|------|------|
| **环境配置** | 4 分 | 环境验证脚本 7/7 通过 |
| **示例运行** | 2 分 | 成功运行 hello_cherryquant.py |
| **目录结构** | 2 分 | 思维导图完整准确 |
| **学习报告** | 2 分 | 报告质量（完整性、深度） |

---

## 常见问题 FAQ

### Q1: Python 版本不是 3.12 可以吗？

A: 最好使用 3.12+，但 3.11 也基本兼容。低于 3.11 可能会有兼容性问题。

### Q2: Docker Desktop 太大，必须安装吗？

A: 对于 Lab 01，可以暂时不启动 Docker，基础示例可以运行。但 Lab 02 开始需要数据库，建议尽早安装。

### Q3: uv sync 很慢怎么办？

A: 可以配置国内镜像:
```bash
# 使用清华镜像
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
uv sync
```

### Q4: Git clone 很慢或失败？

A: 可以使用 GitHub 的镜像站点，或下载 ZIP 包手动解压。

### Q5: 如何重新开始？

A: 删除虚拟环境和 .env 文件，重新配置:
```bash
rm -rf .venv
rm .env
bash scripts/teaching/student_setup.sh
```

---

## 学习资源

- **Module 0**: `docs/course/00_Prerequisites.md`
- **项目 README**: `README.md`
- **学习路径**: `LEARNING_PATH.md`
- **环境配置脚本**: `scripts/teaching/student_setup.sh`
- **验证脚本**: `scripts/teaching/verify_environment.py`

---

**祝实验顺利！遇到问题不要气馁，解决问题本身就是重要的学习过程。🚀**
