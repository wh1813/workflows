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
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# GitHub 网址列表地址
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"
RESTART_INTERVAL = 20

# --- Web Server (保活) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alive")
    def log_message(self, format, *args): pass

def start_web_server():
    try:
        server = HTTPServer(('0.0.0.0', 80), HealthCheckHandler)
        logging.info(">>> [系统] 保活服务已启动")
        server.serve_forever()
    except: pass

# --- 自动更新 ---
def update_urls_from_github():
    try:
        logging.info(">>> 正在检查网址列表更新...")
        resp = requests.get(REMOTE_URLS_PATH, timeout=10)
        if resp.status_code == 200:
            with open("urls.txt", "w", encoding="utf-8") as f:
                f.write(resp.text)
            logging.info("✅ 网址列表更新成功")
    except: pass

# --- 浏览器配置 (核心修改) ---
def get_driver():
    options = Options()
    options.add_argument("--headless") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 【关键修改1】去除"受到自动化软件控制"的提示
    # 这是绝大多数统计代码判断你是机器人的依据
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 【关键修改2】伪造来源 (Referer)，假装是从百度搜索结果点进去的
    # 很多网站不记录直接访问（空来源）的流量
    options.add_argument("--referrer=https://www.baidu.com/")

    # 伪造 User-Agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    service = Service(executable_path="/usr/bin/chromedriver")
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        
        # 【关键修改3】注入 JS 彻底移除 webdriver 特征
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            })
            """
        })
        
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logging.error(f"浏览器启动失败: {e}")
        return None

def run_automation():
    update_urls_from_github()

    if not os.path.exists("urls.txt"): return
    with open("urls.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls: return

    driver = get_driver()
    if not driver: return

    for index, url in enumerate(urls, 1):
        try:
            # 补全协议
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # 定期重启
            if index % RESTART_INTERVAL == 0:
                logging.info(">>> 重启浏览器释放内存...")
                driver.quit()
                time.sleep(2)
                driver = get_driver()
                if not driver: break

            logging.info(f"[{index}/{len(urls)}] 准备访问: {url}")
            driver.get(url)

            # --- 【证据环节】 ---
            # 打印网页标题，证明真的打开了
            page_title = driver.title
            logging.info(f"    ✅ 已打开网页，标题为: 【{page_title}】")
            
            # 如果标题包含"验证"、"安全"、"403"等字眼，说明IP被封了
            if any(k in page_title for k in ["验证", "安全检测", "403", "Forbidden", "Captcha"]):
                logging.warning("    !!! 警告：可能触发了反爬拦截，IP 需要更换 !!!")
            
            # --- 模拟行为 ---
            # 1. 稍微滚动
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            
            # 2. 随机停留 5-8 秒 (稍微加长一点)
            sleep_time = random.uniform(5, 8)
            time.sleep(sleep_time)
            
            # 3. 到底
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            logging.info(f"    -> 模拟阅读完成 (停留 {sleep_time:.1f}s)")

        except Exception as e:
            logging.error(f"    -> 访问出错: {e}")
            try: driver.quit()
            except: pass
            driver = get_driver()
            if not driver: break
            continue

    if driver: driver.quit()
    logging.info(">>> 本轮结束")

if __name__ == "__main__":
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    time.sleep(2)

    while True:
        try:
            run_automation()
        except Exception as e:
            logging.error(f"主程序崩溃: {e}")
        logging.info(">>> 休息 5 分钟...")
        time.sleep(300)
