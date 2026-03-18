# Ai-Testcase Automation Pipeline

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2.0-blue)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

An intelligent automation pipeline that transforms Figma designs into structured Product Requirements Documents (PRDs) and executable Test Cases using Large Language Models (LLMs) and Model Context Protocol (MCP). This project integrates a robust Python backend with a modern React frontend for seamless workflow management.

## 🚀 Key Features

- **Automated Design Parsing**: Extracts design intent and UI elements from Figma files using `fastmcp` and custom parsers.
- **AI-Driven Documentation**: Generates comprehensive PRDs and detailed test cases using OpenAI's GPT-4o.
- **Role-Based Access Control (RBAC)**: Secure API endpoints with JWT authentication and role management (Admin, PM, QA, Designer).
- **Traceability & Coverage**: Bidirectional linking between Requirements and Test Cases with real-time coverage statistics.
- **Audit Logging**: Full audit trail for all critical actions (Design Upload, PRD Generation, Test Case Updates).
- **Interactive Dashboard**: A React-based frontend to visualize workflows, manage artifacts, and export results.
- **Resilient Architecture**: Built with FastAPI, SQLAlchemy (Async), Redis caching, and robust error handling.

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Database**: SQLite (via `aiosqlite` & `SQLAlchemy` async)
- **Caching**: Redis
- **Authentication**: OAuth2 with JWT (`python-jose`, `passlib`)
- **AI Integration**: OpenAI API, LangChain/MCP concepts
- **Security**: `pip-audit`, `bcrypt`

### Frontend
- **Framework**: React 18 + Vite
- **UI Library**: Ant Design
- **State Management**: Zustand
- **Routing**: React Router v6

## 📋 Prerequisites

Ensure you have the following installed on your machine:

- **Python**: 3.10 or higher
- **Node.js**: 18.0.0 or higher
- **npm** or **yarn**
- **Redis Server**: Running locally or accessible via network

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-testcase.git
cd ai-testcase
```

### 2. Backend Setup

It is recommended to use a virtual environment.

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

## 📦 Dependency Management

We use `pip` for dependency management.

### Generate Lock File
To freeze the exact versions of all installed packages for reproducible builds:

```bash
pip freeze > requirements.lock
```

### Security Audit
Run a security audit on your dependencies to check for known vulnerabilities:

```bash
pip-audit -r requirements.txt
```

## 🔧 Configuration

Create a `.env` file in the root directory based on `.env.example`:

```env
# Database Configuration
DATABASE_URL=sqlite+aiosqlite:///./testcase.db

# Security
SECRET_KEY=your_super_secret_key_here_please_change_it
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key-here

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

> **Note**: Replace `your_super_secret_key_here` and `sk-your-openai-api-key-here` with your actual secrets.

## 🚀 Running the Application

### Start the Backend Server

Ensure Redis is running, then from the root directory:

```bash
uvicorn main_api:app --reload --host 0.0.0.0 --port 8000
```

The API documentation will be available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### Start the Frontend Application

Open a new terminal, navigate to the `frontend` directory:

```bash
cd frontend
npm run dev
```

Access the dashboard at: [http://localhost:5173](http://localhost:5173)

## 📂 Directory Structure

```plaintext
ai-testcase/
├── agent_app.py          # AI Agent logic and orchestration
├── agent_tool/           # Helper tools for agents
├── audit.py              # Audit logging implementation
├── auth.py               # Authentication & Authorization (JWT)
├── database.py           # Database connection & session management
├── figma_mcp.py          # Model Context Protocol integration for Figma
├── figma_parser.py       # Custom Figma file parser
├── main_api.py           # Main FastAPI application entry point
├── models.py             # SQLAlchemy database models
├── requirements.txt      # Python dependencies
├── frontend/             # React Frontend source code
│   ├── public/
│   ├── src/
│   │   ├── components/   # Reusable UI components
│   │   ├── pages/        # Application pages
│   │   └── ...
│   └── package.json
└── tests/                # Pytest test suite
    ├── test_flow.py      # Integration tests
    └── ...
```

## 🧪 Testing & Linting

### Run Tests
Run the comprehensive test suite to ensure system integrity.

```bash
# Run tests with coverage report
pytest --cov=. tests/
```

### Linting
Check code quality using Black and Flake8.

```bash
# Format code
black .

# Check style
flake8 .
```

## 🤝 Contributing

Contributions are welcome! Please verify that your changes pass all tests and linting checks.

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Contact

Project Maintainer - [Your Name/Email]

---
*Generated with ❤️ by Trae AI Assistant*
