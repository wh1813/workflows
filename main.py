import os
import time
import logging
import random
import sys
import shutil
import traceback
import requests  # 新增：用于下载更新
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 【配置项】
# 每访问多少个网页后主动重启浏览器（防止内存溢出）
RESTART_INTERVAL = 30 

# 【关键配置】自动更新文件的地址
# 请将下面的链接替换为您 GitHub 仓库中 urls.txt 的 "Raw" 地址
REMOTE_URLS_PATH = "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"

def update_source_code():
    """
    [方案三核心]：启动时自动下载最新的 urls.txt
    """
    print("-" * 50)
    logging.info(">>> [自动更新] 正在检查远程配置更新...")
    
    try:
        # 下载 urls.txt
        logging.info(f"正在下载: {REMOTE_URLS_PATH}")
        resp = requests.get(REMOTE_URLS_PATH, timeout=10)
        
        if resp.status_code == 200:
            # 只有下载成功才覆盖本地文件
            with open("urls.txt", "w", encoding="utf-8") as f:
                f.write(resp.text)
            logging.info("✅ urls.txt 更新成功！已使用最新内容。")
            
            # 打印一下前几行，确认内容对不对
            lines = resp.text.strip().split('\n')
            logging.info(f"当前任务列表包含 {len(lines)} 个网址。")
        else:
            logging.error(f"❌ 下载失败，状态码: {resp.status_code}。将使用镜像内预置的旧文件。")
            
    except Exception as e:
        logging.error(f"❌ 自动更新过程出错: {str(e)}。将使用本地文件继续运行。")
    print("-" * 50)

def get_chrome_options():
    """生成 Chrome 配置选项"""
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
    """创建并初始化浏览器驱动"""
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except:
            pass
            
    try:
        logging.info(">>> 正在启动新浏览器实例...")
        driver = uc.Chrome(
            options=get_chrome_options(),
            version_main=None,
            use_subprocess=True,
            headless=True
        )
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        logging.error(f"创建驱动失败: {str(e)}")
        return None

def close_driver(driver):
    if driver:
        try:
            driver.quit()
        except:
            pass

def run_automation():
    # 1. 先执行自动更新
    update_source_code()
    
    logging.info(">>> 自动化程序启动")
    
    # 2. 读取网址 (此时已经是更新后的文件了)
    url_file = 'urls.txt'
    if not os.path.exists(url_file):
        logging.error(f"错误: 找不到 {url_file}")
        return

    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        logging.warning("urls.txt 为空")
        return

    # 3. 初始化驱动
    driver = create_driver()
    if not driver:
        logging.error("无法启动初始驱动，程序退出")
        return

    # 4. 循环访问
    for index, url in enumerate(urls, 1):
        try:
            # 定期重启
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> 已运行 {RESTART_INTERVAL} 次，执行定期重启释放内存...")
                close_driver(driver)
                time.sleep(5)
                driver = create_driver()
                if not driver: continue

            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            logging.info(f"[{index}/{len(urls)}] 正在访问: {url}")
            
            if driver:
                driver.get(url)
                
                # 模拟行为
                time.sleep(random.uniform(3, 5))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(random.uniform(1, 2))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                wait_time = random.uniform(3, 6)
                logging.info(f"    -> 访问成功 (停留 {wait_time:.1f}s)")
                time.sleep(wait_time)
            else:
                raise WebDriverException("Driver is None")

        except Exception as e:
            # 故障自愈
            logging.warning(f">>> 访问异常 ({str(e)})，正在强制重启浏览器...")
            close_driver(driver)
            time.sleep(5)
            driver = create_driver()
            continue

    close_driver(driver)
    logging.info("所有任务完成。")

if __name__ == "__main__":
    try:
        run_automation()
    except Exception as e:
        print("\n" + "!"*50)
        print("主程序崩溃:")
        traceback.print_exc()
    finally:
        print(">>> 容器进入保活模式...")
        while True:
            time.sleep(3600)
