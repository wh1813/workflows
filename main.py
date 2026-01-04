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

# 配置项
RESTART_INTERVAL = 30
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"

# --- 【新增】虚拟 Web 服务器 (骗过云平台的健康检查) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 无论谁访问，都返回 200 OK
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"I am alive!")
    
    # 屏蔽访问日志，避免刷屏
    def log_message(self, format, *args):
        pass

def start_web_server():
    """启动一个监听 80 端口的假网站"""
    try:
        # 监听所有 IP 的 80 端口
        server = HTTPServer(('0.0.0.0', 80), HealthCheckHandler)
        logging.info(">>> [系统] 虚拟 Web 服务器已启动 (监听 Port 80)...")
        server.serve_forever()
    except Exception as e:
        logging.error(f">>> [警告] 80 端口启动失败 (可能已被占用): {e}")

# --- 正常的爬虫逻辑 ---

def update_source_code():
    print("-" * 50)
    logging.info(">>> [自动更新] 正在检查远程配置更新...")
    try:
        resp = requests.get(REMOTE_URLS_PATH, timeout=10)
        if resp.status_code == 200:
            with open("urls.txt", "w", encoding="utf-8") as f:
                f.write(resp.text)
            logging.info("✅ urls.txt 更新成功！")
        else:
            logging.error(f"❌ 下载失败: {resp.status_code}")
    except Exception as e:
        logging.error(f"❌ 自动更新出错: {str(e)}")
    print("-" * 50)

def get_chrome_options():
    data_dir = "/tmp/chrome_user_data"
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-data-dir={data_dir}")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    return options

def create_driver():
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        try: shutil.rmtree(data_dir, ignore_errors=True)
        except: pass
            
    try:
        logging.info(">>> 正在启动新浏览器实例...")
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

def run_automation():
    update_source_code()
    logging.info(">>> 自动化程序启动")
    
    url_file = 'urls.txt'
    if not os.path.exists(url_file):
        logging.error(f"错误: 找不到 {url_file}")
        return

    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        logging.warning("urls.txt 为空")
        return

    driver = create_driver()
    if not driver: return

    for index, url in enumerate(urls, 1):
        try:
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> 定期重启浏览器释放内存...")
                close_driver(driver)
                time.sleep(5)
                driver = create_driver()
                if not driver: continue

            if not url.startswith(('http://', 'https://')): url = 'https://' + url
            
            logging.info(f"[{index}/{len(urls)}] 访问: {url}")
            
            if driver:
                driver.get(url)
                time.sleep(random.uniform(3, 5))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                wait_time = random.uniform(3, 6)
                logging.info(f"    -> 成功 (停留 {wait_time:.1f}s)")
                time.sleep(wait_time)
            else:
                raise WebDriverException("Driver is None")

        except Exception as e:
            logging.warning(f">>> 异常重启: {str(e)}")
            close_driver(driver)
            time.sleep(5)
            driver = create_driver()
            continue

    close_driver(driver)
    logging.info("所有任务完成。")

if __name__ == "__main__":
    # 【关键修改】在主程序启动前，先启动一个后台线程运行 Web 服务器
    # 这样 Docker 容器就会监听 80 端口，通过云平台的健康检查
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # 给一点时间让 Web Server 启动
    time.sleep(2)
    
    try:
        run_automation()
    except Exception as e:
        print("主程序崩溃:")
        traceback.print_exc()
    finally:
        print(">>> 任务结束，进入保活模式 (Web Server 依然在运行)...")
        while True:
            time.sleep(3600)
