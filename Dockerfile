# 1. 使用官方 Python 3.9 轻量版镜像
FROM python:3.9-slim

# 2. 环境变量设置
# PYTHONUNBUFFERED=1: 强制 Python 实时打印日志，不缓存 (解决无日志问题)
ENV PYTHONUNBUFFERED=1
# PYTHONDONTWRITEBYTECODE=1: 不生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1

# 设置容器内工作目录
WORKDIR /app

# 3. 安装系统基础工具
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 4. 安装 Google Chrome Stable
# 使用 .deb 包直接安装，让 apt 自动解决依赖 (libxss1, fonts-liberation 等)
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 5. 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 复制项目所有代码
COPY . .

# 7. 【关键修改】启动命令
# 逻辑：尝试运行 Python -> 无论成功还是失败 -> 打印分隔线 -> 进入无限休眠
# 这样容器永远是 "Active" 状态，你可以随时查看 Logs 排查报错
CMD ["sh", "-c", "python main.py; echo '\n>>> 程序运行结束或发生崩溃'; echo '>>> 容器正在休眠保活，请检查上方日志...'; sleep infinity"]
