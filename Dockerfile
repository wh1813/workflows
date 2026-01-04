# 使用官方 Python slim 镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 1. 安装基础工具 (只安装最核心的，不手动装 Chrome 依赖)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 2. 添加 Google Chrome 官方源并安装
# 这一步会自动处理 libxss1, libappindicator 等所有依赖，不需要手动写
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制程序代码
COPY . .

# 5. 启动命令
CMD ["python", "main.py"]
