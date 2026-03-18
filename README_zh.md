# Ai-Testcase 自动化流水线

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2.0-blue)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

一个智能自动化流水线，利用大型语言模型（LLMs）和模型上下文协议（MCP），将 Figma 设计转化为结构化的产品需求文档（PRDs）和可执行的测试用例。本项目集成了强大的 Python 后端与现代化的 React 前端，实现无缝的工作流管理。

## 🚀 核心功能

- **自动化设计解析**：使用 `fastmcp` 和自定义解析器从 Figma 文件中提取设计意图和 UI 元素。
- **AI 驱动文档生成**：利用 OpenAI 的 GPT-4o 生成全面的 PRD 和详细的测试用例。
- **基于角色的访问控制（RBAC）**：通过 JWT 认证和角色管理（管理员、产品经理、测试人员、设计师）保障 API 端点安全。
- **可追溯性与覆盖率**：实现需求与测试用例之间的双向链接，并提供实时覆盖率统计。
- **审计日志**：对所有关键操作（设计上传、PRD 生成、测试用例更新）进行完整审计记录。
- **交互式仪表盘**：基于 React 的前端界面，用于可视化工作流、管理产物和导出结果。
- **高可用架构**：基于 FastAPI、SQLAlchemy（异步）、Redis 缓存构建，具备健壮的错误处理机制。

## 🛠️ 技术栈

### 后端
- **框架**：FastAPI (Python 3.10+)
- **数据库**：SQLite (通过 `aiosqlite` & `SQLAlchemy` 异步访问)
- **缓存**：Redis
- **认证**：OAuth2 with JWT (`python-jose`, `passlib`)
- **AI 集成**：OpenAI API, LangChain/MCP 概念
- **安全**：`pip-audit`, `bcrypt`

### 前端
- **框架**：React 18 + Vite
- **UI 组件库**：Ant Design
- **状态管理**：Zustand
- **路由**：React Router v6

## 📋 先决条件

确保您的机器上已安装以下软件：

- **Python**: 3.10 或更高版本
- **Node.js**: 18.0.0 或更高版本
- **npm** 或 **yarn**
- **Redis Server**: 本地运行或通过网络可访问

## ⚙️ 安装指南

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/ai-testcase.git
cd ai-testcase
```

### 2. 后端设置

建议使用虚拟环境。

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 前端设置

```bash
cd frontend
npm install
```

## 📦 依赖管理

我们使用 `pip` 进行依赖管理。

### 生成锁文件
锁定所有安装包的确切版本以实现可复现构建：

```bash
pip freeze > requirements.lock
```

### 安全审计
对依赖项进行安全审计以检查已知漏洞：

```bash
pip-audit -r requirements.txt
```

## 🔧 配置

基于 `.env.example` 在根目录下创建 `.env` 文件：

```env
# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./testcase.db

# 安全配置
SECRET_KEY=your_super_secret_key_here_please_change_it
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key-here

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

> **注意**：请将 `your_super_secret_key_here` 和 `sk-your-openai-api-key-here` 替换为您实际的密钥。

## 🚀 运行应用

### 启动后端服务器

确保 Redis 正在运行，然后在根目录下执行：

```bash
uvicorn main_api:app --reload --host 0.0.0.0 --port 8000
```

API 文档地址：[http://localhost:8000/docs](http://localhost:8000/docs)

### 启动前端应用

打开一个新的终端，进入 `frontend` 目录：

```bash
cd frontend
npm run dev
```

访问仪表盘：[http://localhost:5173](http://localhost:5173)

## 📂 目录结构

```plaintext
ai-testcase/
├── agent_app.py          # AI Agent 逻辑与编排
├── agent_tool/           # Agent 辅助工具
├── audit.py              # 审计日志实现
├── auth.py               # 认证与授权 (JWT)
├── database.py           # 数据库连接与会话管理
├── figma_mcp.py          # Figma 模型上下文协议集成
├── figma_parser.py       # 自定义 Figma 文件解析器
├── main_api.py           # FastAPI 应用主入口
├── models.py             # SQLAlchemy 数据库模型
├── requirements.txt      # Python 依赖
├── frontend/             # React 前端源代码
│   ├── public/
│   ├── src/
│   │   ├── components/   # 可复用 UI 组件
│   │   ├── pages/        # 应用页面
│   │   └── ...
│   └── package.json
└── tests/                # Pytest 测试套件
    ├── test_flow.py      # 集成测试
    └── ...
```

## 🧪 测试与代码规范

### 运行测试
运行全面的测试套件以确保系统完整性。

```bash
# 运行测试并生成覆盖率报告
pytest --cov=. tests/
```

### 代码规范检查
使用 Black 和 Flake8 检查代码质量。

```bash
# 格式化代码
black .

# 检查代码风格
flake8 .
```

## 🤝 贡献指南

欢迎贡献！请确保您的更改通过所有测试和代码规范检查。

1.  Fork 本仓库。
2.  创建您的特性分支 (`git checkout -b feature/AmazingFeature`)。
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)。
4.  推送到分支 (`git push origin feature/AmazingFeature`)。
5.  开启 Pull Request。

## 📄 许可证

本项目基于 MIT 许可证开源 - 详情请参阅 [LICENSE](LICENSE) 文件。

## 📞 联系方式

项目维护者 - [Your Name/Email]

---
*Generated with ❤️ by Trae AI Assistant*
