# 1. 基础镜像
FROM python:3.9-slim

# 2. 环境变量 (确保日志实时输出)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 3. 安装 Chromium 浏览器和驱动
# 使用系统自带的包管理器安装，这是最稳定、体积最小的方案
RUN apt-get update && apt-get install -y \
    wget \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 4. 安装 Python 库
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制代码
COPY . .

# 6. 暴露端口 (骗过云平台健康检查)
EXPOSE 80

# 7. 启动命令
CMD ["python", "main.py"]
