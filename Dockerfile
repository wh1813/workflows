# 使用官方 Python slim 镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 1. 更新 apt 并安装 wget (仅用于下载)
RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 2. 直接下载 Chrome .deb 包并使用 apt 安装
# 说明：使用 apt install ./xxx.deb 会自动解决所有依赖问题
# 这种方式避开了 keys、gnupg 和 source.list 的所有坑
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制程序代码
COPY . .

# 5. 启动命令
CMD ["python", "main.py"]
