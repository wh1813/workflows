import os
import time
import logging
import random
import sys
import threading
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- 配置区 ---
# GitHub 上 urls.txt 的 RAW 地址 (请确保这个地址是准确的)
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"

# 多少个网页重启一次浏览器 (防止内存溢出)
RESTART_INTERVAL = 20

# --- 模块1: 虚拟 Web 服务器 (防止云平台杀容器) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"I am alive!")
    def log_message(self, format, *args): pass

def start_web_server():
    try:
        # 监听 80 端口
        server = HTTPServer(('0.0.0.0', 80), HealthCheckHandler)
        logging.info(">>> [系统] 保活 Web 服务器已启动 (Port 80)")
        server.serve_forever()
    except Exception as e:
        logging.warning(f">>> [警告] 80 端口可能被占用: {e}")

# --- 模块2: 自动更新 urls.txt ---
def update_urls_from_github():
    print("-" * 50)
    logging.info(">>> [自动更新] 正在从 GitHub 获取最新网址列表...")
    try:
        resp = requests.get(REMOTE_URLS_PATH, timeout=10)
        if resp.status_code == 200:
            # 只有获取成功才覆盖本地文件
            with open("urls.txt", "w", encoding="utf-8") as f:
                f.write(resp.text)
            logging.info("✅ urls.txt 更新成功！")
        else:
            logging.error(f"❌ 下载失败，状态码: {resp.status_code}")
    except Exception as e:
        logging.error(f"❌ 更新出错 (可能是网络问题): {e}")
    print("-" * 50)

# --- 模块3: 浏览器控制 ---
def get_driver():
    options = Options()
    # Docker 环境必须参数
    options.add_argument("--headless") # 无头模式
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # 模拟 User-Agent (防止被认为是 Python 脚本)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Dockerfile 中安装的驱动路径
    service = Service(executable_path="/usr/bin/chromedriver")
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30) # 页面加载超时限制
        return driver
    except Exception as e:
        logging.error(f"浏览器初始化失败: {e}")
        return None

def run_automation():
    # 1. 先尝试更新网址
    update_urls_from_github()

    # 2. 读取网址
    if not os.path.exists("urls.txt"):
        logging.error("没有找到 urls.txt，请检查 GitHub 地址或文件上传")
        return

    with open("urls.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        logging.warning("urls.txt 是空的")
        return

    logging.info(f">>> 开始执行任务，共 {len(urls)} 个网址")

    # 3. 启动浏览器
    driver = get_driver()
    if not driver: return

    for index, url in enumerate(urls, 1):
        try:
            # 补全协议
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # 定期重启浏览器释放内存
            if index % RESTART_INTERVAL == 0:
                logging.info(">>> 正在重启浏览器以清理内存...")
                driver.quit()
                time.sleep(2)
                driver = get_driver()
                if not driver: break

            logging.info(f"[{index}/{len(urls)}] 访问: {url}")
            driver.get(url)

            # --- 模拟真人行为 (关键计数逻辑) ---
            
            # 1. 稍微滚动一下 (触发很多懒加载的统计代码)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            
            # 2. 随机停留 4-7 秒 (您要求的)
            sleep_time = random.uniform(4, 7)
            logging.info(f"    -> 停留 {sleep_time:.2f} 秒 (模拟阅读)")
            time.sleep(sleep_time)
            
            # 3. 再滚到底部
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        except Exception as e:
            logging.error(f"    -> 访问出错: {e}")
            # 如果浏览器死机了，尝试重启
            try:
                driver.quit()
            except: pass
            driver = get_driver()
            if not driver: break
            continue

    if driver:
        driver.quit()
    logging.info(">>> 本轮任务全部完成")

if __name__ == "__main__":
    # 1. 启动保活 Web Server (守护线程)
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # 给一点时间让 Server 启动
    time.sleep(2)

    # 2. 主循环
    while True:
        try:
            run_automation()
        except Exception as e:
            logging.error(f"主程序崩溃: {e}")
        
        logging.info(">>> 休息 10 分钟后开始下一轮...")
        time.sleep(600)
