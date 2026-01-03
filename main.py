import os
import time
import logging
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import InvalidArgumentException

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_random_user_agent():
    # 简单的随机 UA 池，避免每次都是同一个
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
    ]
    return random.choice(uas)

def run_automation():
    # 2. 设置 Chrome 运行参数
    chrome_options = Options()
    
    # 【核心修改1】：使用新版无头模式 (headless=new)，这比旧版 headless 更像真实浏览器
    chrome_options.add_argument("--headless=new") 
    
    # Docker 环境基础参数
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # 【核心修改2】：设置分辨率，防止因窗口为 0x0 或 800x600 被判定为机器人
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 【核心修改3】：隐藏自动化控制条和自动化扩展特征
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # 禁用 Blink 引擎中的自动化特性
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # 指定容器内路径 (保持你原有的配置)
    chrome_options.binary_location = "/usr/bin/chromium"
    
    # 随机 User-Agent
    chrome_options.add_argument(f"--user-agent={get_random_user_agent()}")

    driver = None
    try:
        logging.info("正在初始化浏览器驱动...")
        
        service = Service(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # 【核心修改4】：通过 CDP 命令彻底抹除 navigator.webdriver 标记
        # 这是所有反爬检测的第一道门槛
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            })
            """
        })
        
        logging.info("浏览器启动成功，反检测脚本已注入。")
        
        # 3. 读取网址
        url_file = 'urls.txt'
        if not os.path.exists(url_file):
            logging.error(f"找不到 {url_file}")
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            logging.warning("urls.txt 为空")
            return

        # 4. 循环访问
        for index, url in enumerate(urls, 1):
            try:
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                logging.info(f"[{index}/{len(urls)}] 访问: {url}")
                driver.get(url)
                
                # 【核心修改5】：模拟真人行为 (滚动页面)
                # 很多统计代码是“懒加载”的，只有滚动了才开始记录
                logging.info(">>> 正在模拟浏览行为...")
                
                # 随机停留 2-4 秒
                time.sleep(random.uniform(2, 4))
                
                # 向下滚动一半
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(random.uniform(1, 2))
                
                # 滚动到底部
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                logging.info(f"完成访问: {url}")
                
            except InvalidArgumentException:
                logging.error(f"URL 错误: {url}")
            except Exception as e:
                logging.error(f"访问异常: {str(e)}")
                
    except Exception as e:
        logging.error(f"程序崩溃: {str(e)}")
    finally:
        if driver:
            driver.quit()
            logging.info("浏览器已关闭。")
        
        logging.info("任务完成，保持容器在线...")
        while True:
            time.sleep(3600)

if __name__ == "__main__":
    run_automation()
