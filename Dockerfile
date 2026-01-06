# 1. 基础镜像
FROM python:3.9-slim

# 2. 环境变量 (确保日志实时输出)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 3. 安装依赖和官方 Google Chrome
# 注意：这里换回了 google-chrome-stable，因为 undetected-chromedriver 需要它
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 下载并安装官方 Chrome (能解决依赖问题)
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 4. 安装 Python 库
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制代码
COPY . .

# 6. 暴露端口 (配合 main.py 里的 Web Server 保活)
EXPOSE 80

# 7. 启动命令
CMD ["python", "main.py"]
