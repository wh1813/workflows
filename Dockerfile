# 1. 基础镜像
FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 2. 安装 Chrome, 常用工具, 和 Xray (翻译器)
# 增加 unzip 用于解压 Xray
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    procps \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 安装官方 Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 【核心】下载并安装 Xray (VLESS 转换核心)
# 下载 -> 解压 -> 赋予权限 -> 移到 /usr/bin
RUN wget -q https://github.com/XTLS/Xray-core/releases/download/v1.8.4/Xray-linux-64.zip \
    && unzip Xray-linux-64.zip \
    && mv xray /usr/bin/xray \
    && chmod +x /usr/bin/xray \
    && rm Xray-linux-64.zip

# 3. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制代码
COPY . .

# 5. 暴露端口
EXPOSE 80

# 6. 启动
CMD ["python", "main.py"]
