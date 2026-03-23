# Ai-Testcase 自动化流水线

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2.0-blue)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

一个智能自动化流水线，使用大模型（LLMs）与 Model Context Protocol (MCP)，将 Figma 设计转化为结构化 PRD 与可执行测试用例。项目集成了稳健的 Python 后端和现代 React 前端，支持完整的设计到测试流程。

## 关键能力
- **自动设计解析**：使用 `fastmcp` 与自定义解析器提取 Figma 设计意图与 UI 元素。
- **AI 生成文档**：基于 OpenAI 模型生成 PRD 与测试用例。
- **角色权限控制**：JWT 认证与角色管理（Admin/PM/QA/Designer）。
- **可追溯性与覆盖率**：需求与用例双向关联，提供覆盖率统计。
- **审计日志**：设计上传、PRD/用例生成、更新等关键行为可审计。
- **交互式面板**：React 前端可视化工作流与结果导出。
- **高可用架构**：FastAPI + SQLAlchemy(Async) + Redis 缓存。

## 技术栈
### 后端
- **框架**：FastAPI (Python 3.10+)
- **数据库**：SQLite (`aiosqlite` + SQLAlchemy async)
- **缓存**：Redis
- **认证**：OAuth2 + JWT (`python-jose`, `passlib`)
- **AI 集成**：OpenAI API, LangChain/MCP 概念
- **安全**：`pip-audit`, `bcrypt`

### 前端
- **框架**：React 18 + Vite
- **UI**：Ant Design
- **状态**：Zustand
- **路由**：React Router v6

## 先决条件
- **Python**：3.10 或更高
- **Node.js**：18.0.0 或更高
- **npm** 或 **yarn**
- **Redis**：本地或可访问服务

## 安装
### 1. 克隆仓库
```bash
git clone https://github.com/yourusername/ai-testcase.git
cd ai-testcase
```

### 2. 后端环境
```bash
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. 前端环境
```bash
cd frontend
npm install
```

## 依赖管理
### 生成锁文件
```bash
pip freeze > requirements.lock
```

### 安全审计
```bash
pip-audit -r requirements.txt
```

## 配置
基于 `.env.example` 创建 `.env`：
```env
DATABASE_URL=sqlite+aiosqlite:///./testcase.db

SECRET_KEY=your_super_secret_key_here_please_change_it
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

OPENAI_API_KEY=sk-your-openai-api-key-here

FIGMA_TOKEN=figma-personal-access-token-here
ENABLE_FIGMA_VISION=true

OPENAI_VISION_MODEL=gpt-4o
OPENAI_FUSION_MODEL=gpt-4o
OPENAI_TIMEOUT_SEC=120

FIGMA_LAYER_LIMIT=1500
FUSION_MAX_CHARS=50000
PROMPT_MAX_CHARS=50000

COMPARE_SIM_THRESHOLD=0.55
VISION_TEXT_THRESHOLD=0.35

ENABLE_FLOWCHART_CV=true
ENABLE_FLOWCHART_VISION=true

FLOW_NODE_MIN_W=200
FLOW_NODE_MIN_H=200
FLOW_NODE_IGNORE_REGEX=Background|BG|Stroke|Mask|Shadow|Glow
FLOWCHART_MAX_NODES=15
FLOWCHART_MAX_TEXTS=80
FLOW_NODE_PROMPT_MAX_CHARS=15000
FLOW_NODE_INCLUDE_REGEX=Start|Join|Joining|Record|Recording|Initiat|Init|Meeting
FIGMA_IMAGE_TIMEOUT_SEC=60
FIGMA_IMAGE_RETRY=2
FIGMA_PROXY=http://127.0.0.1:7890
```

## 运行
### 启动后端
```bash
uvicorn main_api:app --reload --host 0.0.0.0 --port 8000
```
访问 API 文档：`http://localhost:8000/docs`

### 启动前端
```bash
cd frontend
npm run dev
```
访问前端：`http://localhost:5173`

## 目录结构
```plaintext
ai-testcase/
├── agent_app.py
├── agent_tool/
├── audit.py
├── auth.py
├── database.py
├── figma_mcp.py
├── figma_parser.py
├── main_api.py
├── models.py
├── requirements.txt
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/
│       └── pages/
└── tests/
```

## 测试与规范
### 测试
```bash
pytest --cov=. tests/
```

### 格式化与风格检查
```bash
black .
flake8 .
```

## 贡献
1. Fork 仓库
2. 新建分支 (`git checkout -b feature/AmazingFeature`)
3. 提交 (`git commit -m 'Add some AmazingFeature'`)
4. 推送 (`git push origin feature/AmazingFeature`)
5. 发起 PR

## 许可证
MIT 许可证，详见 [LICENSE](LICENSE)

## 联系方式
维护者：Your Name/Email

---
*Generated with ❤️ by Trae AI Assistant*
