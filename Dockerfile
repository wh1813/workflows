# 1. 基础镜像
FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 2. 安装基础工具
# 避免使用国内源以防止 GitHub Actions 网络报错
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    procps \
    unzip \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装 Chrome 浏览器
# 直接从 Google 官方下载最新稳定版
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 4. 下载并安装 Xray
RUN wget -q https://github.com/XTLS/Xray-core/releases/download/v1.8.4/Xray-linux-64.zip \
    && unzip Xray-linux-64.zip \
    && mv xray /usr/bin/xray \
    && chmod +x /usr/bin/xray \
    && rm Xray-linux-64.zip

# 5. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 复制代码
COPY . .

# 7. 暴露端口
EXPOSE 80

# 8. 启动命令
CMD ["python", "main.py"]
