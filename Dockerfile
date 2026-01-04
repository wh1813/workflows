# 1. 使用官方 Python 基础镜像
FROM python:3.9-slim

# 2. 【关键】设置环境变量：禁止 Python 缓存输出，确保能在控制台看到日志
ENV PYTHONUNBUFFERED=1
# 防止 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1

# 设置工作目录
WORKDIR /app

# 3. 安装 wget (用于下载 Chrome)
RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 4. 【关键】直接下载并安装 Chrome .deb 包
# 这种方式会自动解决所有依赖 (libxss1, fonts 等)，不会报错
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 5. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 复制程序代码
COPY . .

# 7. 启动命令
CMD ["python", "main.py"]
