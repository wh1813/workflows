# workflows
my-bot

loko219/web-bot:latest



PYTHONUNBUFFERED=1


可以计数的版本，后续可以基于此进行迭代
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
import urllib.parse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= 配置区域 =================
# 1. 网址列表 (GitHub Raw)
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"

# 2. 节点列表 (GitHub Raw)
REMOTE_XRAY_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/xray.txt"

# 3. 每访问多少个网页切换一次 IP (建议 30-50)
RESTART_INTERVAL = 50
# ===========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- 模块1: VLESS 链接解析器 ---
def parse_vless(url):
    try:
        if not url.startswith("vless://"): return None
        main_part = url.split("://")[1].split("?")[0].split("#")[0]
        query_part = url.split("?")[1].split("#")[0] if "?" in url else ""
        user_info, host_port = main_part.split("@")
        host, port = host_port.split(":")
        params = dict(urllib.parse.parse_qsl(query_part))
        return {
            "uuid": user_info,
            "address": host,
            "port": int(port),
            "type": params.get("type", "tcp"),
            "security": params.get("security", "none"),
            "sni": params.get("sni", ""),
            "path": params.get("path", "/"),
            "host": params.get("host", ""),
            "fp": params.get("fp", "")
        }
    except Exception as e:
        logging.error(f"解析节点链接失败: {e}")
        return None

# --- 模块2: 代理服务管理 (Xray) ---
def check_proxy_connectivity():
    try:
        proxies = {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}
        r = requests.get("https://www.baidu.com", proxies=proxies, timeout=5)
        if r.status_code == 200: return True
    except: return False
    return False

def start_xray_with_node(node_url):
    node = parse_vless(node_url)
    if not node: return False
    
    config = {
        "log": {"loglevel": "error"},
        "inbounds": [{"port": 10808, "listen": "127.0.0.1", "protocol": "http", "settings": {"udp": True}}],
        "outbounds": [{
            "protocol": "vless",
            "settings": {"vnext": [{"address": node["address"], "port": node["port"], "users": [{"id": node["uuid"], "encryption": "none"}]}]},
            "streamSettings": {
                "network": node["type"],
                "security": node["security"],
                "tlsSettings": {"serverName": node["sni"], "fingerprint": node["fp"]} if node["security"] == "tls" else None,
                "wsSettings": {"path": node["path"], "headers": {"Host": node["host"]}} if node["type"] == "ws" else None
            }
        }]
    }

    with open("config.json", "w") as f: json.dump(config, f)
    subprocess.run("pkill -9 -f xray", shell=True, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    try:
        subprocess.Popen(["xray", "-c", "config.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        if check_proxy_connectivity():
            logging.info(f"    -> [节点切换成功] 目标地址: {node['address']}")
            return True
        else:
            logging.warning(f"    -> [节点不可用] 无法联网，跳过")
            return False
    except Exception as e:
        logging.error(f"Xray 启动错误: {e}")
        return False

def rotate_proxy():
    if not os.path.exists("xray.txt"): return False
    with open("xray.txt", "r") as f:
        nodes = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    if not nodes: return False
    random.shuffle(nodes)
    logging.info(f">>> [代理] 正在从 {len(nodes)} 个节点中寻找可用节点...")
    for node_url in nodes:
        if start_xray_with_node(node_url): return True
    logging.error("!!! 所有节点均测试失败，请检查 xray.txt !!!")
    return False

# --- 模块3: 自动更新 ---
def update_remote_files():
    files = {"urls.txt": REMOTE_URLS_PATH, "xray.txt": REMOTE_XRAY_PATH}
    for filename, url in files.items():
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(filename, "w", encoding="utf-8") as f: f.write(r.text)
                logging.info(f"✅ {filename} 更新成功")
        except: pass

# --- 模块4: 强力清理 ---
def force_kill_chrome():
    subprocess.run("pkill -9 -f chrome", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -9 -f undetected_chromedriver", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("rm -rf /tmp/.org.chromium.*", shell=True, stderr=subprocess.DEVNULL)

# --- 模块5: 浏览器配置 (核心优化版) ---
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
    options.add_argument("--ignore-certificate-errors")
    
    # 强制不缓存 (关键设置)
    options.add_argument("--disk-cache-size=1")
    options.add_argument("--media-cache-size=1")
    
    # 挂载 Xray 代理
    options.add_argument("--proxy-server=http://127.0.0.1:10808")

    try:
        # 指定版本 144
        driver = uc.Chrome(options=options, version_main=144, use_subprocess=True, headless=True)
        
        # 【关键】伪造 Referer：让网站以为你是从百度搜索点进来的
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
            "headers": {
                "Referer": "https://www.baidu.com/link?url=KkKS_fake_search_result",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            }
        })
        
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        logging.error(f"浏览器启动失败: {e}")
        force_kill_chrome()
        return None

# --- 增强版交互逻辑 (结合了点击和滚动) ---
def simulate_interaction(driver):
    try:
        # 1. 刚进去，假装愣神几秒 (等待统计JS加载)
        time.sleep(random.uniform(3, 5))

        # 2. 模拟中途滚动
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(random.uniform(2, 4))

        # 3. 【核心】尝试点击“继续阅读/展开”按钮
        # 这是为了应对 Book118/Renren 的折叠机制
        try:
            # 查找常见的展开按钮 (根据经验总结的 Class)
            buttons = driver.find_elements(By.CSS_SELECTOR, ".more-btn, .read-more, .banner-more-btn, #moreBtn, div.fc2e")
            if buttons:
                btn = buttons[0]
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btn)
                logging.info("    🖱️ 触发【继续阅读】成功")
                time.sleep(2)
        except: pass

        # 4. 滚动到底部
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # 5. 最后停留，确保时长达标
        sleep_time = random.uniform(5, 8)
        time.sleep(sleep_time)
        
        logging.info(f"    ✅ 交互完成 (停留 {sleep_time:.1f}s)")

    except Exception as e:
        logging.warning(f"    ⚠️ 交互轻微异常: {e}")

# --- 主逻辑 ---
def run_automation():
    update_remote_files()

    if subprocess.call("pgrep -f xray > /dev/null", shell=True) != 0:
        if not rotate_proxy(): return 

    if not os.path.exists("urls.txt"): return
    with open("urls.txt", "r") as f: urls = [l.strip() for l in f if l.strip()]
    if not urls: return

    driver = get_driver()
    if not driver: return

    logging.info(f">>> 任务开始，共 {len(urls)} 个链接")

    for index, url in enumerate(urls, 1):
        try:
            if not url.startswith('http'): url = 'https://' + url

            # IP 轮换逻辑
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> [维护] 已访问 {index} 个，正在切换节点并重启...")
                try: driver.quit()
                except: pass
                if not rotate_proxy(): break 
                driver = get_driver()
                if not driver: break

            # 访问页面
            logging.info(f"[{index}/{len(urls)}] 访问: {url}")
            driver.get(url)
            
            # 执行增强版交互
            simulate_interaction(driver)

        except Exception as e:
            logging.error(f"    -> 错误: {e}")
            try: driver.quit()
            except: pass
            logging.warning(">>> 异常恢复中，切换节点...")
            rotate_proxy()
            driver = get_driver()
            if not driver: break

    try: driver.quit()
    except: pass
    force_kill_chrome()

# --- 保活 Web Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Alive")
    def log_message(self, format, *args): pass

if __name__ == "__main__":
    threading.Thread(target=HTTPServer(('0.0.0.0', 80), HealthCheckHandler).serve_forever, daemon=True).start()
    
    update_remote_files()
    if not rotate_proxy():
        logging.error("启动失败：无可用节点")
        time.sleep(60)
    
    while True:
        try: run_automation()
        except: pass
        logging.info("💤 本轮结束，休息 10 分钟...")
        time.sleep(600)
