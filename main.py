import os
import time
import logging
import random
import sys
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import InvalidArgumentException, WebDriverException

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- 代理配置 (关键) ---
# 如果您在本地电脑运行，v2rayN 默认 HTTP 端口通常是 10809 或 10808
# 如果您在 Docker/云服务器运行，您不能直接用 127.0.0.1，具体请看代码下方的解释
PROXY_IP = ""  # 例如 "127.0.0.1:10809"，留空则不使用代理

def get_driver():
    chrome_options = Options()
    
    # Docker 环境必备参数
    chrome_options.add_argument("--headless") # 无头模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # 模拟真实浏览器 User-Agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # --- 设置代理 ---
    if PROXY_IP:
        logging.info(f"正在配置代理: {PROXY_IP}")
        chrome_options.add_argument(f'--proxy-server=http://{PROXY_IP}')

    # Docker 中使用系统预装的驱动
    service = Service(executable_path="/usr/bin/chromedriver")
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logging.error(f"初始化失败: {e}")
        return None

def run_task():
    # 1. 读取 urls.txt
    if not os.path.exists('urls.txt'):
        logging.error("找不到 urls.txt 文件，请上传！")
        return

    with open('urls.txt', 'r', encoding='utf-8') as file:
        urls = [line.strip() for line in file if line.strip()]

    if not urls:
        logging.warning("urls.txt 是空的")
        return

    # 2. 启动浏览器
    driver = get_driver()
    if not driver:
        return

    try:
        for i, url in enumerate(urls, 1):
            try:
                # 补全 URL
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url

                logging.info(f"[{i}/{len(urls)}] Opening: {url}")
                driver.get(url)
                
                # --- 核心修改：随机停留 4-7 秒 ---
                sleep_time = random.uniform(4, 7)
                logging.info(f"    -> 随机停留 {sleep_time:.2f} 秒...")
                time.sleep(sleep_time)

            except InvalidArgumentException:
                logging.error(f"无效 URL: {url}")
            except Exception as e:
                logging.error(f"访问错误: {e}")
                
                # 如果浏览器崩了，尝试重启
                try:
                    driver.quit()
                except: pass
                driver = get_driver()

    finally:
        if driver:
            driver.quit()
            logging.info("任务结束，浏览器已关闭")

if __name__ == "__main__":
    # 为了防止 Docker 跑完退出，加个循环
    while True:
        run_task()
        logging.info("所有网址访问完毕，休息 1 小时后重新开始...")
        time.sleep(3600)
