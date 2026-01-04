# 使用官方 Python slim 镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 1. 安装必要的系统依赖
# wget: 下载Chrome
# gnupg: 密钥管理
# unzip: 解压
# xvfb, libxi6, libgconf-2-4: Chrome 运行需要的显示库
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装官方 Google Chrome Stable (不再使用 Chromium)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# 3. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制程序代码
COPY . .

# 5. 启动命令
CMD ["python", "main.py"]
