import os
import time
import logging
import random
import sys
import shutil
import traceback
import threading
import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 【配置项】
# 核心修改：将重启间隔从 30 降低到 10，防止 100MB 磁盘写满
RESTART_INTERVAL = 10 
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"

# --- 虚拟 Web 服务器 (保活用) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")
    def log_message(self, format, *args): pass

def start_web_server():
    try:
        server = HTTPServer(('0.0.0.0', 80), HealthCheckHandler)
        server.serve_forever()
    except: pass

# --- 爬虫逻辑 ---

def update_source_code():
    try:
        resp = requests.get(REMOTE_URLS_PATH, timeout=10)
        if resp.status_code == 200:
            with open("urls.txt", "w", encoding="utf-8") as f:
                f.write(resp.text)
            logging.info("✅ 列表更新成功")
    except: pass

def get_chrome_options():
    data_dir = "/tmp/chrome_user_data"
    
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--window-size=1920,1080")
    
    # 【核心修改】磁盘空间极简优化
    options.add_argument("--disk-cache-size=1")  # 限制磁盘缓存仅 1 字节
    options.add_argument("--media-cache-size=1") # 限制媒体缓存
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-offline-load-stale-cache")
    options.add_argument("--incognito") # 尝试使用隐身模式减少数据写入
    
    options.add_argument(f"--user-data-dir={data_dir}")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    return options

def create_driver():
    # 启动前强制清理垃圾
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        try: shutil.rmtree(data_dir, ignore_errors=True)
        except: pass
            
    try:
        logging.info(">>> 启动新浏览器 (已优化存储)...")
        driver = uc.Chrome(options=get_chrome_options(), version_main=None, use_subprocess=True, headless=True)
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        logging.error(f"创建驱动失败: {str(e)}")
        return None

def close_driver(driver):
    if driver:
        try: driver.quit()
        except: pass
    # 关闭后再次清理垃圾，确保不残留
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        try: shutil.rmtree(data_dir, ignore_errors=True)
        except: pass

def run_automation():
    update_source_code()
    
    url_file = 'urls.txt'
    if not os.path.exists(url_file): return

    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    driver = create_driver()
    if not driver: return

    for index, url in enumerate(urls, 1):
        try:
            # 每 10 个就重启清理一次，防止 100MB 爆满
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> 周期性清理 (已访问 {index} 个)...")
                close_driver(driver)
                time.sleep(2)
                driver = create_driver()
                if not driver: continue

            if not url.startswith(('http://', 'https://')): url = 'https://' + url
            
            logging.info(f"[{index}/{len(urls)}] {url}")
            
            if driver:
                driver.get(url)
                # 稍微缩短停留时间，减少缓存生成
                time.sleep(random.uniform(2, 4))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
            else:
                raise WebDriverException("Driver丢失")

        except Exception as e:
            logging.warning(f"错误重启: {str(e)}")
            close_driver(driver)
            time.sleep(3)
            driver = create_driver()
            continue

    close_driver(driver)
    logging.info("任务完成")

if __name__ == "__main__":
    # 启动保活 Web Server
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    time.sleep(2)
    
    try:
        run_automation()
    except Exception as e:
        traceback.print_exc()
    finally:
        while True: time.sleep(3600)
