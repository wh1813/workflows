import os
import time
import logging
import random
import sys
import shutil
import threading
import requests
import undetected_chromedriver as uc  # 【关键】使用这个库才能计数
from selenium.common.exceptions import WebDriverException
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- 配置区 ---
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"
# 【关键防崩设置】每访问 10 个网页就重启一次，防止硬盘/内存爆满
RESTART_INTERVAL = 10

# --- 模块: Web Server (保活) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")
    def log_message(self, format, *args): pass

def start_web_server():
    try:
        server = HTTPServer(('0.0.0.0', 80), HealthCheckHandler)
        logging.info(">>> [系统] 保活服务已启动 (Port 80)")
        server.serve_forever()
    except: pass

# --- 模块: 自动更新 ---
def update_urls_from_github():
    try:
        logging.info(">>> 正在检查网址列表更新...")
        resp = requests.get(REMOTE_URLS_PATH, timeout=10)
        if resp.status_code == 200:
            with open("urls.txt", "w", encoding="utf-8") as f:
                f.write(resp.text)
            logging.info("✅ 网址列表更新成功")
    except: pass

# --- 模块: 浏览器配置 (高伪装版) ---
def get_driver():
    # 每次启动前强制清理缓存目录 (解决硬盘爆满的关键)
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        try: shutil.rmtree(data_dir, ignore_errors=True)
        except: pass

    options = uc.ChromeOptions()
    options.add_argument("--headless=new") # 新版无头
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 【防崩溃核心】限制磁盘写入，防止 100MB 瞬间写满
    options.add_argument("--disk-cache-size=1")
    options.add_argument("--media-cache-size=1")
    options.add_argument("--disable-application-cache")
    
    # 指定数据目录到 /tmp
    options.add_argument(f"--user-data-dir={data_dir}")

    # 【伪装核心】
    # 1. 伪造 User-Agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    
    # 2. 自动下载并匹配驱动 (undetected_chromedriver 的特性)
    try:
        # use_subprocess=True 是 Docker 里不僵死的关键
        driver = uc.Chrome(options=options, version_main=None, use_subprocess=True, headless=True)
        
        # 3. 伪造 Referer (假装来自百度)
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
            "headers": {
                "Referer": "https://www.baidu.com/" 
            }
        })
        
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logging.error(f"浏览器启动失败: {e}")
        return None

# --- 主逻辑 ---
def run_automation():
    update_urls_from_github()

    if not os.path.exists("urls.txt"):
        logging.error("未找到 urls.txt")
        return

    with open("urls.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls: return

    # 初始启动
    driver = get_driver()
    if not driver: return

    for index, url in enumerate(urls, 1):
        try:
            # 补全 URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # 【防崩溃】定期重启清理
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> 已访问 {index} 个，重启清理内存/硬盘...")
                if driver:
                    try: driver.quit()
                    except: pass
                time.sleep(2)
                driver = get_driver()
                if not driver: break

            logging.info(f"[{index}/{len(urls)}] 访问: {url}")
            driver.get(url)

            # 【验证】打印标题
            logging.info(f"    ✅ 标题: 【{driver.title}】")
            
            # 模拟真人行为 (这部分逻辑保留您之前的)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            
            # 随机停留 4-7 秒
            sleep_time = random.uniform(4, 7)
            time.sleep(sleep_time)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            logging.info(f"    -> 完成 (停留 {sleep_time:.1f}s)")

        except Exception as e:
            logging.error(f"    -> 出错: {e}")
            # 故障自愈
            try: driver.quit()
            except: pass
            driver = get_driver()
            if not driver: break
            continue

    if driver:
        try: driver.quit()
        except: pass
    logging.info(">>> 本轮任务结束")

if __name__ == "__main__":
    # 启动 Web Server 保活
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    time.sleep(2)

    while True:
        try:
            run_automation()
        except Exception as e:
            logging.error(f"主程序崩溃: {e}")
        logging.info(">>> 休息 10 分钟...")
        time.sleep(600)
