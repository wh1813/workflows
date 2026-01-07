# 1. 基础镜像
FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 2. 安装 Chrome 和 必备工具 (新增 procps 用于杀进程)
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 安装 Chrome Stable
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 代码
COPY . .

EXPOSE 80

CMD ["python", "main.py"]
