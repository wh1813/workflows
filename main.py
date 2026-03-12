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
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By  # 用于查找页面元素
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= 配置区域 =================
# 1. 网址列表的 GitHub Raw 地址
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"

# 2. 节点列表的 GitHub Raw 地址 (一行一个 vless:// 链接)
REMOTE_XRAY_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/xray.txt"

# 3. 每访问多少个网页切换一次 IP (建议 50-100)
RESTART_INTERVAL = 50
# ===========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- 【新增】自动检测系统自带的 Chrome 版本 ---
def get_chrome_version():
    """获取系统安装的 Chrome 主版本号"""
    try:
        # 尝试通过命令行获取 Google Chrome 版本
        result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
        version_string = result.stdout.strip()
        # 解析出主版本号，例如从 "Google Chrome 146.0.7680.71" 提取 "146"
        match = re.search(r'Chrome/(\d+)', version_string)
        if not match:
            match = re.search(r'Google Chrome (\d+)', version_string)
        if match:
            return int(match.group(1))
    except Exception as e:
        logging.warning(f"无法自动检测 Chrome 版本，将使用备用版本号: {e}")
    return 146  # 默认降级方案

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

# --- 模块2: 代理服务管理 (Xray) ---
def check_proxy_connectivity():
    """测试当前代理是否通畅 (访问百度)"""
    try:
        proxies = {
            "http": "http://127.0.0.1:10808",
            "https": "http://127.0.0.1:10808"
        }
        # 5秒超时
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
        # 后台启动 xray
        subprocess.Popen(["xray", "-c", "config.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) # 等待启动
        
        # 启动后立刻进行健康检查
        if check_proxy_connectivity():
            logging.info(f"    -> [节点切换成功] 目标地址: {node['address']}")
            return True
        else:
            logging.warning(f"    -> [节点不可用] 无法联网，跳过: {node['address']}")
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

    # 随机打乱节点顺序
    random.shuffle(nodes)

    logging.info(f">>> [代理] 正在从 {len(nodes)} 个节点中寻找可用节点...")

    for node_url in nodes:
        # 尝试启动并检查，如果成功则直接返回
        if start_xray_with_node(node_url):
            return True
    
    logging.error("!!! 所有节点均测试失败，请检查 xray.txt !!!")
    return False

# --- 模块3: 自动更新 ---
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

# --- 模块4: 强力清理 (防止僵尸进程及缓存冲突) ---
def force_kill_chrome():
    subprocess.run("pkill -9 -f chrome", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -9 -f undetected_chromedriver", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("rm -rf /tmp/.org.chromium.*", shell=True, stderr=subprocess.DEVNULL)
    # 删除 undetected_chromedriver 的历史缓存驱动，强制重新下载匹配当前浏览器的驱动
    subprocess.run("rm -rf ~/.local/share/undetected_chromedriver", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("rm -rf /root/.local/share/undetected_chromedriver", shell=True, stderr=subprocess.DEVNULL)

# --- 模块5: 浏览器配置 (已修复SSL报错 & 自动版本适配) ---
def get_driver():
    force_kill_chrome()
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir): shutil.rmtree(data_dir, ignore_errors=True)

    # 获取当前系统的 Chrome 主版本号
    chrome_major_version = get_chrome_version()

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-data-dir={data_dir}")
    
    # 忽略 SSL 证书错误
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    
    # 强制走本地 Xray 代理
    options.add_argument("--proxy-server=http://127.0.0.1:10808")

    # 资源限制
    options.add_argument("--disk-cache-size=1")
    options.add_argument("--media-cache-size=1")
    
    # 【深度优化】动态伪装 User-Agent
    user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_major_version}.0.0.0 Safari/537.36"
    options.add_argument(f"--user-agent={user_agent}")

    try:
        # 动态传入 version_main
        driver = uc.Chrome(options=options, version_main=chrome_major_version, use_subprocess=True, headless=True)
        
        # 伪装 Referer
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

    # 2. 确保代理运行 (如果进程不在，或者需要初始化，先转起来)
    if subprocess.call("pgrep -f xray > /dev/null", shell=True) != 0:
        if not rotate_proxy(): return 

    if not os.path.exists("urls.txt"): return
    with open("urls.txt", "r") as f: urls = [l.strip() for l in f if l.strip()]
    if not urls: return

    driver = get_driver()
    if not driver: return

    logging.info(f">>> 任务开始")

    for index, url in enumerate(urls, 1):
        try:
            if not url.startswith('http'): url = 'https://' + url

            # 【轮换逻辑】每 RESTART_INTERVAL 次重启并切换 IP
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> [维护] 已访问 {index} 个，正在切换节点并重启...")
                try: driver.quit()
                except: pass
                
                # 切换节点
                if not rotate_proxy():
                    logging.error("没有可用节点，本轮中止")
                    break 
                
                driver = get_driver()
                if not driver: break

            # 【验证当前 IP】
            if index % RESTART_INTERVAL == 1 or index == 1:
                try:
                    driver.get("https://api.ipify.org")
                    time.sleep(2)
                    current_ip = driver.find_element(By.TAG_NAME, "body").text
                    logging.info(f"    🔎 [身份查验] 当前公网IP: 【{current_ip}】")
                except Exception as e:
                    logging.warning(f"    ⚠️ 查IP超时 (不影响后续访问): {e}")

            logging.info(f"[{index}/{len(urls)}] 访问: {url}")
            driver.get(url)
            
            logging.info(f"    ✅ 标题: 【{driver.title}】")

            # 模拟行为
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            sleep_time = random.uniform(5, 8)
            time.sleep(sleep_time)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            logging.info(f"    -> 成功 (停留 {sleep_time:.1f}s)")

        except Exception as e:
            logging.error(f"    -> 错误: {e}")
            try: driver.quit()
            except: pass
            
            logging.warning(">>> 检测到异常，尝试切换节点...")
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
    # 启动 80 端口保活
    threading.Thread(target=HTTPServer(('0.0.0.0', 80), HealthCheckHandler).serve_forever, daemon=True).start()
    
    # 首次启动时，先下载配置并找一个可用节点
    update_remote_files()
    if not rotate_proxy():
        logging.error("启动失败：xray.txt 无可用节点")
        time.sleep(60)
    
    while True:
        try: run_automation()
        except: pass
        time.sleep(600)
