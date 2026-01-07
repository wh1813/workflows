import os
import time
import logging
import random
import sys
import shutil
import threading
import subprocess
import json
import requests
import undetected_chromedriver as uc
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= 配置区域 =================
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"
RESTART_INTERVAL = 50

# 【核心】VLESS 节点配置
# 我已经根据您提供的链接帮您填好了。如果以后换节点，只需要改这里。
VLESS_CONFIG = {
    "uuid": "95f67697-971e-4139-8a87-24a6472302d3",
    "address": "freeyx.cloudflare88.eu.org",
    "port": 443,
    "sni": "ai.wh1813.de5.net",
    "host": "ai.wh1813.de5.net",
    "path": "/?ed=2048"
}
# ===========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- 模块1: 代理服务管理 (Xray) ---
def start_vless_proxy():
    """生成配置文件并启动 Xray 内核"""
    logging.info(">>> [代理] 正在配置 VLESS 节点...")
    
    # 1. 生成 Xray 配置文件 (config.json)
    # 监听本地 10808 端口，将流量转发到您的 VLESS 节点
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": 10808,
            "listen": "127.0.0.1",
            "protocol": "http", # 转换为 HTTP 代理供 Chrome 使用
            "settings": {"udp": True}
        }],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": VLESS_CONFIG["address"],
                    "port": VLESS_CONFIG["port"],
                    "users": [{"id": VLESS_CONFIG["uuid"], "encryption": "none"}]
                }]
            },
            "streamSettings": {
                "network": "ws",
                "security": "tls",
                "tlsSettings": {"serverName": VLESS_CONFIG["sni"]},
                "wsSettings": {
                    "path": VLESS_CONFIG["path"],
                    "headers": {"Host": VLESS_CONFIG["host"]}
                }
            }
        }]
    }

    # 写入配置文件
    with open("config.json", "w") as f:
        json.dump(config, f)

    # 2. 杀掉旧进程
    subprocess.run("pkill -9 -f xray", shell=True, stderr=subprocess.DEVNULL)
    
    # 3. 启动 Xray
    try:
        # 在后台启动
        subprocess.Popen(["xray", "-c", "config.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(">>> [代理] VLESS 代理服务已启动 (127.0.0.1:10808)")
        # 等待2秒让它连接
        time.sleep(2)
        return True
    except Exception as e:
        logging.error(f"!!! Xray 启动失败: {e}")
        return False

# --- 模块2: 强力清理 ---
def force_kill_chrome():
    subprocess.run("pkill -9 -f chrome", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -9 -f undetected_chromedriver", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("rm -rf /tmp/.org.chromium.*", shell=True, stderr=subprocess.DEVNULL)

# --- 模块3: 浏览器 ---
def get_driver():
    force_kill_chrome()
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir): shutil.rmtree(data_dir, ignore_errors=True)

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-data-dir={data_dir}")
    
    # 【核心】告诉 Chrome 使用我们刚才搭建的本地代理
    options.add_argument("--proxy-server=http://127.0.0.1:10808")

    # 资源限制
    options.add_argument("--disk-cache-size=1")
    options.add_argument("--media-cache-size=1")

    # 伪装
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    try:
        driver = uc.Chrome(options=options, version_main=None, use_subprocess=True, headless=True)
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"Referer": "https://www.baidu.com/link?url=KkKS"}})
        driver.set_page_load_timeout(60) # 代理可能慢，超时设长一点
        return driver
    except Exception as e:
        logging.error(f"浏览器启动失败: {e}")
        force_kill_chrome()
        return None

# --- 主逻辑 ---
def run_automation():
    # 0. 确保代理在运行
    # (如果 xray 挂了，这里重启它，但不频繁重启)
    if subprocess.call("pgrep -f xray > /dev/null", shell=True) != 0:
        start_vless_proxy()

    # 1. 更新网址
    try:
        r = requests.get(REMOTE_URLS_PATH, timeout=10)
        if r.status_code == 200:
            with open("urls.txt", "w", encoding="utf-8") as f: f.write(r.text)
            logging.info("✅ 网址列表更新成功")
    except: pass

    if not os.path.exists("urls.txt"): return
    with open("urls.txt", "r") as f: urls = [l.strip() for l in f if l.strip()]
    if not urls: return

    driver = get_driver()
    if not driver: return

    logging.info(f">>> 开始执行任务 (使用代理模式)")

    for index, url in enumerate(urls, 1):
        try:
            if not url.startswith('http'): url = 'https://' + url

            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> [维护] 重启清理...")
                try: driver.quit()
                except: pass
                driver = get_driver()
                if not driver: break

            logging.info(f"[{index}/{len(urls)}] 访问: {url}")
            driver.get(url)
            
            # 打印标题，确认代理是否通畅 (如果代理不通，这里会报错或显示错误页)
            logging.info(f"    ✅ 标题: 【{driver.title}】")

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            sleep_time = random.uniform(5, 8)
            time.sleep(sleep_time)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            logging.info(f"    -> 成功 (停留 {sleep_time:.1f}s)")

        except Exception as e:
            logging.error(f"    -> 错误: {e}")
            try: driver.quit()
            except: pass
            driver = get_driver()
            if not driver: break

    try: driver.quit()
    except: pass
    force_kill_chrome()

# --- 保活 ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Alive")
    def log_message(self, format, *args): pass

def start_web_server():
    try:
        server = HTTPServer(('0.0.0.0', 80), HealthCheckHandler)
        server.serve_forever()
    except: pass

if __name__ == "__main__":
    threading.Thread(target=start_web_server, daemon=True).start()
    
    # 程序启动时先启动代理
    start_vless_proxy()
    
    while True:
        try: run_automation()
        except: pass
        time.sleep(600)
