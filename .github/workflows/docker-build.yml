# 1. 使用官方 Python 轻量镜像作为基础
FROM python:3.9-slim

# 2. 安装运行 Chrome 浏览器所需的系统依赖和浏览器本身
# 这些依赖库是运行无头浏览器（Headless Chrome）必须的
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    chromium \
    chromium-driver \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 3. 设置容器内的工作目录
WORKDIR /app

# 4. 复制依赖清单并安装 Python 库
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制当前目录下的所有文件（main.py, urls.txt 等）到容器内
COPY . .

# 6. 设置环境变量，确保 Python 能够实时输出日志到控制台
ENV PYTHONUNBUFFERED=1

# 7. 容器启动时执行的命令
CMD ["python", "main.py"]
