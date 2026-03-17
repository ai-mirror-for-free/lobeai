# LobeAI 项目启动指南

## 📋 项目概述

- **项目名称**: LobeAI
- **框架**: FastAPI
- **端口**: 25141
- **依赖数据库**: PostgreSQL
- **主入口**: `main.py`

---

## 🔧 前置要求

### 系统要求
- Python 3.8+
- PostgreSQL 12+
- pip 包管理器

### 检查 Python 版本
```bash
python --version
# 或
python3 --version
```

---

## 📦 安装步骤

### 1. 安装依赖包

```bash
cd /Users/yangfan/project/lobeai

# 使用 pip 安装依赖
pip install -r requirements.txt

# 或使用 pip3
pip3 install -r requirements.txt
```

**依赖包说明**:
- `fastapi`: 异步 Web 框架
- `pydantic`: 数据验证库
- `requests`: HTTP 客户端
- `psycopg2-binary`: PostgreSQL 数据库驱动
- `pandas`: 数据处理
- `openpyxl`: Excel 文件处理
- `email-validator`: 邮箱验证
- `python-dotenv`: 环境变量管理

### 2. 验证依赖安装

```bash
pip list | grep -E "fastapi|pydantic|requests|psycopg2|pandas|openpyxl|email-validator"
```

---

## 🗄️ 数据库配置

### PostgreSQL 连接信息

根据 `.env` 文件配置，有两种模式可选：

#### 模式 1: 连接到远程服务器（生产环境）
```
DB_HOST=www.yang-sjq.cn
DB_PORT=2543
DB_USERNAME=postgres
DB_PASSWORD=yf3816547290
```

#### 模式 2: 连接到本地数据库（开发环境）
```
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=postgres
DB_PASSWORD=your_password
```

### 切换数据库配置

编辑 `.env` 文件，取消注释需要的配置：

```bash
# 生产环境
DB_HOST=www.yang-sjq.cn
DB_PORT=2543

# 本地开发（注释上面的行，取消注释下面的行）
# DB_HOST=localhost
# DB_PORT=5432
```

### 验证数据库连接

```bash
# 使用 psql 命令行工具测试连接
psql -h www.yang-sjq.cn -p 2543 -U postgres -d postgres

# 或使用 Python 测试
python3 -c "
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        user=os.getenv('DB_USERNAME'),
        password=os.getenv('DB_PASSWORD'),
        database='postgres'
    )
    print('✓ 数据库连接成功')
    conn.close()
except Exception as e:
    print(f'✗ 连接失败: {e}')
"
```

---

## ⚙️ 环境变量配置

### 当前 `.env` 文件内容

```ini
# 管理员账号
ADMIN_USERNAME=yang
ADMIN_EMAIL=yf13755921935@gmail.com
ADMIN_PASSWORD=yf3816547290

# API 基础 URL
BASE_URL=https://chat.yang-sjq.cn
# BASE_URL=http://localhost:8080

# PostgreSQL 配置
DB_HOST=www.yang-sjq.cn
# DB_HOST=localhost
DB_PORT=2543
DB_USERNAME=postgres
DB_PASSWORD=yf3816547290
DB_CHARSET=utf8mb4

# NewAPI 服务器配置
NEWAPI_URL=https://api.yang-sjq.cn
# NEWAPI_URL=http://localhost:3000
NEWAPI_USER=yang
NEWAPI_PASSWORD=Yf@3816547290
```

### 常用配置说明

| 环境变量 | 用途 | 示例 |
|---------|------|------|
| `ADMIN_USERNAME` | 管理员用户名 | `yang` |
| `ADMIN_PASSWORD` | 管理员密码 | `yf3816547290` |
| `BASE_URL` | API 基础地址 | `https://chat.yang-sjq.cn` |
| `DB_HOST` | 数据库主机 | `www.yang-sjq.cn` |
| `DB_PORT` | 数据库端口 | `2543` |
| `NEWAPI_URL` | NewAPI 服务器地址 | `https://api.yang-sjq.cn` |

---

## 🚀 启动项目

### 方式 1: 直接运行（简单快速）

```bash
cd /Users/yangfan/project/lobeai

python main.py
```

**预期输出**:
```
INFO:     Uvicorn running on http://0.0.0.0:25141 (Press CTRL+C to quit)
INFO:     Application startup complete
```

### 方式 2: 使用 uvicorn 运行（推荐用于开发）

```bash
# 基本运行
uvicorn main:app --host 0.0.0.0 --port 25141

# 带自动重启功能（代码修改时自动重启）
uvicorn main:app --host 0.0.0.0 --port 25141 --reload

# 带调试模式
uvicorn main:app --host 0.0.0.0 --port 25141 --reload --log-level debug
```

### 方式 3: 在后台运行

```bash
# 使用 nohup（日志保存到 nohup.out）
nohup python main.py > logs/app.log 2>&1 &

# 使用 screen（可以后续重新连接）
screen -S lobeai
cd /Users/yangfan/project/lobeai
python main.py
# 按 Ctrl+A 然后 D 可以离开 screen，但程序继续运行

# 使用 tmux（类似 screen，更现代）
tmux new-session -d -s lobeai
tmux send-keys -t lobeai "cd /Users/yangfan/project/lobeai && python main.py" Enter
```

---

## ✅ 验证服务

### 1. 健康检查

```bash
curl http://localhost:25141/health
```

**预期响应**:
```json
{
  "status": "healthy"
}
```

### 2. 测试发送验证码接口

```bash
curl -X POST "http://localhost:25141/api/send-verification-code" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### 3. 查看 API 文档

启动后访问以下 URL：
- **Swagger UI**: http://localhost:25141/docs
- **ReDoc**: http://localhost:25141/redoc

---

## 📁 项目结构

```
lobeai/
├── main.py                    # 应用入口
├── requirements.txt           # 项目依赖
├── .env                       # 环境变量配置
├── STARTUP_GUIDE.md          # 本启动指南
├── docs/                     # API 文档目录
│   ├── API_接口文档.md       # 接口文档
│   └── new_api接口文档.txt   # NewAPI 文档
├── services/                 # 业务逻辑服务
│   ├── NewAPIClient.py       # NewAPI 客户端
│   └── creater_users.py      # 用户创建脚本
├── tools/                    # 工具模块
│   ├── logger_manager.py     # 日志管理
│   └── vaild.py             # 数据验证模型
├── logs/                     # 应用日志输出
└── data/                     # 数据存储目录
```

---

## 🐛 常见问题排查

### 问题 1: 依赖安装失败

```bash
# 升级 pip
pip install --upgrade pip

# 清除 pip 缓存后重新安装
pip install --no-cache-dir -r requirements.txt

# 或使用 pip3
pip3 install -r requirements.txt
```

### 问题 2: 数据库连接失败

```bash
# 检查数据库是否可访问
ping www.yang-sjq.cn

# 检查端口是否开放
nc -zv www.yang-sjq.cn 2543

# 查看 .env 文件中的配置是否正确
cat .env | grep DB_
```

### 问题 3: 端口被占用

```bash
# 查看端口 25141 是否被占用
lsof -i :25141

# 如果被占用，可以选择其他端口运行
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 问题 4: 模块找不到

```bash
# 确保在项目目录下运行
cd /Users/yangfan/project/lobeai

# 确保依赖已安装
pip list

# 检查 Python 路径
python -c "import sys; print(sys.path)"
```

### 问题 5: 邮件发送失败

```bash
# 检查 NewAPI 服务器地址是否正确
curl https://api.yang-sjq.cn/health

# 检查认证凭证
# NEWAPI_USER=yang
# NEWAPI_PASSWORD=Yf@3816547290
```

---

## 📊 日志查看

### 查看实时日志

```bash
# 项目内日志
tail -f logs/app.log

# 系统日志
tail -f nohup.out
```

### 清除旧日志

```bash
# 清除 logs 目录下的所有日志
rm logs/*.log

# 或保留最近 7 天的日志
find logs/ -name "*.log" -mtime +7 -delete
```

---

## 🛑 停止服务

### 方式 1: 直接运行时
```bash
# 按 Ctrl+C 即可停止
```

### 方式 2: 后台运行时
```bash
# 查找进程
ps aux | grep main.py

# 杀死进程
kill -9 <PID>

# 或使用 screen/tmux
screen -S lobeai -X quit
tmux kill-session -t lobeai
```

---

## 📈 性能优化

### 增加工作进程

```bash
# 使用 4 个 worker 进程
uvicorn main:app --host 0.0.0.0 --port 25141 --workers 4
```

### 调整超时时间

```bash
# 增加 timeout（默认 60 秒）
uvicorn main:app --host 0.0.0.0 --port 25141 --timeout-keep-alive 120
```

---

## 🔐 安全建议

1. **修改默认密码**
   - 更新 `.env` 中的 `ADMIN_PASSWORD`
   - 更新 `NEWAPI_PASSWORD`

2. **使用 HTTPS**
   - 在生产环境中使用 HTTPS
   - 配置 SSL 证书

3. **限制 API 访问**
   - 配置防火墙规则
   - 使用 IP 白名单

4. **备份环境文件**
   ```bash
   # 备份 .env 文件（不要提交到 Git）
   cp .env .env.backup
   ```

---

## 📞 获取帮助

如有问题，请参考：
- 项目 GitHub: https://github.com/QuantumNous/new-api
- API 文档: https://apifox.newapi.ai/
- 接口文档: `/docs/API_接口文档.md`

---

**最后更新**: 2026-03-17
