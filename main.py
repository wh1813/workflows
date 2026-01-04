import os
import time
import logging
import random
import sys
import shutil
import traceback
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

# 【配置项】每访问多少个网页后主动重启浏览器（防止内存溢出）
RESTART_INTERVAL = 30 

def get_chrome_options():
    """生成 Chrome 配置选项"""
    # 清理缓存目录，防止权限冲突
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
    # 禁用加载图片以节省大量内存和带宽 (可选，不需要看图的话建议开启)
    # options.add_argument("--blink-settings=imagesEnabled=false") 
    return options

def create_driver():
    """创建并初始化浏览器驱动"""
    data_dir = "/tmp/chrome_user_data"
    # 每次创建前清理旧目录
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
        # 设置页面加载超时时间为 60秒，防止死等
        driver.set_page_load_timeout(60)
        return driver
    except Exception as e:
        logging.error(f"创建驱动失败: {str(e)}")
        return None

def close_driver(driver):
    """安全关闭驱动"""
    if driver:
        try:
            driver.quit()
        except:
            pass

def run_automation():
    print("-" * 50)
    logging.info(">>> 自动化程序启动 (带自动重启机制)")
    
    # 读取网址
    url_file = 'urls.txt'
    if not os.path.exists(url_file):
        logging.error(f"错误: 找不到 {url_file}")
        return

    with open(url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        logging.warning("urls.txt 为空")
        return

    # 初始化驱动
    driver = create_driver()
    if not driver:
        logging.error("无法启动初始驱动，程序退出")
        return

    # 循环访问
    for index, url in enumerate(urls, 1):
        try:
            # --- 1. 定期重启机制 (Proactive Restart) ---
            if index % RESTART_INTERVAL == 0:
                logging.info(f">>> 已运行 {RESTART_INTERVAL} 次，正在执行定期重启以释放内存...")
                close_driver(driver)
                time.sleep(5) # 等待进程完全释放
                driver = create_driver()
                if not driver:
                    logging.error("重启驱动失败，尝试跳过...")
                    continue

            # 补全协议
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            logging.info(f"[{index}/{len(urls)}] 正在访问: {url}")
            
            # --- 2. 访问逻辑 ---
            if driver:
                driver.get(url)
                
                # 模拟行为
                time.sleep(random.uniform(3, 5))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(random.uniform(1, 2))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                wait_time = random.uniform(3, 5)
                logging.info(f"    -> 访问成功 (停留 {wait_time:.1f}s)")
                time.sleep(wait_time)
            else:
                logging.error("驱动丢失，准备重建...")
                raise WebDriverException("Driver is None")

        except Exception as e:
            # --- 3. 故障自愈机制 (Reactive Restart) ---
            # 如果遇到 Read timed out 或其他严重错误，立即重启浏览器
            logging.error(f"!!! 访问出错 ({str(e)})")
            logging.warning(">>> 检测到浏览器异常/超时，正在强制重启浏览器...")
            
            close_driver(driver)
            time.sleep(5) # 冷却
            driver = create_driver() # 重建连接
            
            if driver:
                logging.info(">>> 浏览器已恢复，准备处理下一个任务")
            else:
                logging.error(">>> 浏览器恢复失败！")
            
            # 记录错误但不中断整个循环
            continue

    # 结束
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
