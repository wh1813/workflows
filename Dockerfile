# 1. 基础镜像
FROM python:3.9-slim

# 2. 环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 3. 安装工具和 Chrome
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 4. 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 代码
COPY . .

# 【关键修改】声明暴露 80 端口
EXPOSE 80

# 6. 启动
CMD ["sh", "-c", "python main.py; echo '\n>>> 进程意外退出'; sleep infinity"]
