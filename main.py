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
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= 配置区域 =================
# 1. 网址列表的 GitHub Raw 地址
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"

# 2. 节点列表的 GitHub Raw 地址 (一行一个 vless:// 链接)
REMOTE_XRAY_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/xray.txt"

# 3. 每访问多少个网页切换一次 IP
RESTART_INTERVAL = 50
# ===========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- 模块1: VLESS 链接解析器 ---
def parse_vless(url):
    """将 vless:// 字符串解析为 Xray 配置字典"""
    try:
        if not url.startswith("vless://"): return None
        
        # 解析基础部分 user@host:port
        main_part = url.split("://")[1].split("?")[0].split("#")[0]
        query_part = url.split("?")[1].split("#")[0] if "?" in url else ""
        
        user_info, host_port = main_part.split("@")
        host, port = host_port.split(":")
        
        # 解析参数
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

# --- 模块2: 代理服务管理 (带健康检查) ---
def check_proxy_connectivity():
    """测试当前代理是否通畅"""
    try:
        # 尝试通过代理访问百度，超时设为 5 秒
        proxies = {
            "http": "http://127.0.0.1:10808",
            "https": "http://127.0.0.1:10808"
        }
        r = requests.get("https://www.baidu.com", proxies=proxies, timeout=5)
        if r.status_code == 200:
            return True
    except:
        return False
    return False

def start_xray_with_node(node_url):
    """配置并启动 Xray，返回是否成功"""
    node = parse_vless(node_url)
    if not node: return False
    
    # 构造 config.json
    config = {
        "log": {"loglevel": "error"},
        "inbounds": [{"port": 10808, "listen": "127.0.0.1", "protocol": "http", "settings": {"udp": True}}],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": node["address"],
                    "port": node["port"],
                    "users": [{"id": node["uuid"], "encryption": "none"}]
                }]
            },
            "streamSettings": {
                "network": node["type"],
                "security": node["security"],
                "tlsSettings": {"serverName": node["sni"], "fingerprint": node["fp"]} if node["security"] == "tls" else None,
                "wsSettings": {"path": node["path"], "headers": {"Host": node["host"]}} if node["type"] == "ws" else None
            }
        }]
    }

    # 写入配置
    with open("config.json", "w") as f: json.dump(config, f)

    # 重启 Xray 进程
    subprocess.run("pkill -9 -f xray", shell=True, stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        subprocess.Popen(["xray", "-c", "config.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) # 等待启动
        
        # 【关键】启动后立刻进行健康检查
        if check_proxy_connectivity():
            logging.info(f"    -> [检测通过] 节点可用: {node['address']}")
            return True
        else:
            logging.warning(f"    -> [检测失败] 节点无法联网，将跳过: {node['address']}")
            return False
            
    except Exception as e:
        logging.error(f"Xray 启动错误: {e}")
        return False

def rotate_proxy():
    """读取文件并轮换到一个可用的节点"""
    if not os.path.exists("xray.txt"):
        logging.error("未找到 xray.txt，无法启动代理")
        return False

    with open("xray.txt", "r") as f:
        # 过滤空行和注释
        nodes = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not nodes:
        logging.error("xray.txt 是空的")
        return False

    # 随机打乱节点顺序，避免每次都从第一个开始试
    random.shuffle(nodes)

    logging.info(f">>> [代理] 正在从 {len(nodes)} 个节点中寻找可用节点...")

    for node_url in nodes:
        # 尝试启动并检查
        if start_xray_with_node(node_url):
            return True # 找到一个能用的，结束寻找
    
    logging.error("!!! 所有节点均测试失败，请检查 xray.txt !!!")
    return False

# --- 模块3: 自动更新 (支持 urls.txt 和 xray.txt) ---
def update_remote_files():
    files = {
        "urls.txt": REMOTE_URLS_PATH,
        "xray.txt": REMOTE_XRAY_PATH
    }
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

# --- 模块5: 浏览器 ---
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
    
    # 强制走本地 Xray 代理
    options.add_argument("--proxy-server=http://127.0.0.1:10808")

    options.add_argument("--disk-cache-size=1")
    options.add_argument("--media-cache-size=1")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    try:
        driver = uc.Chrome(options=options, version_main=None, use_subprocess=True, headless=True)
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"Referer": "https://www.baidu.com/link?url=KkKS"}})
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        logging.error(f"浏览器启动失败: {e}")
        force_kill_chrome()
        return None

# --- 主逻辑 ---
def run_automation():
    # 1. 更新配置文件
    update_remote_files()

    # 2. 确保有一个可用的代理正在运行
    # 如果进程不存在，或者为了轮换 IP，我们需要重新启动代理
    # 注意：这里我们简单判断，如果 xray 没运行，或者需要轮换，就执行 rotate_proxy
    if subprocess.call("pgrep -f xray > /dev/null", shell=True) != 0:
        if not rotate_proxy(): return # 如果找不到可用节点，暂停任务

    if not os.path.exists("urls.txt"): return
    with open("urls.txt", "r") as f: urls = [l.strip() for l in f if l.strip()]
    if not urls: return

    driver = get_driver()
    if not driver: return

    logging.info(f">>> 任务开始")

    for index, url in enumerate(urls, 1):
        try:
            if not url.startswith('http'): url = 'https://' + url

            # 【轮换逻辑】
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> [维护] 已访问 {index} 个，正在切换节点并重启...")
                try: driver.quit()
                except: pass
                
                # 尝试切换到一个新节点
                if not rotate_proxy():
                    logging.error("没有可用节点，休息一会儿...")
                    break 
                
                driver = get_driver()
                if not driver: break

            logging.info(f"[{index}/{len(urls)}] 访问: {url}")
            driver.get(url)
            
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
            
            # 如果访问出错 (可能是当前节点突然挂了)，立即尝试切换节点
            logging.warning(">>> 检测到网络错误，尝试更换节点...")
            rotate_proxy()
            
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

if __name__ == "__main__":
    threading.Thread(target=HTTPServer(('0.0.0.0', 80), HealthCheckHandler).serve_forever, daemon=True).start()
    
    # 首次启动先找一个好节点
    update_remote_files()
    rotate_proxy()
    
    while True:
        try: run_automation()
        except: pass
        time.sleep(600)
