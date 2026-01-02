import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import InvalidArgumentException

# 1. 配置日志输出，方便在 ClawCloud 控制台查看运行状态
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_automation():
    # 2. 设置 Chrome 运行参数（针对 Docker 环境深度优化）
    chrome_options = Options()
    chrome_options.add_argument("--headless")           # 必须：无头模式
    chrome_options.add_argument("--no-sandbox")          # 必须：容器权限
    chrome_options.add_argument("--disable-dev-shm-usage") # 必须：防止内存溢出
    chrome_options.add_argument("--disable-gpu")
    
    # 显式指定容器内 Chromium 浏览器的安装路径
    chrome_options.binary_location = "/usr/bin/chromium"

    # 模拟真实浏览器 User-Agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        logging.info("正在初始化浏览器驱动...")
        
        # 【关键修改】：不再使用 webdriver_manager，直接指向系统预装的驱动路径
        # 这个路径由 Dockerfile 中的 apt-get install chromium-driver 产生
        service = Service(executable_path="/usr/bin/chromedriver")
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("浏览器环境启动成功！已绕过版本匹配问题。")
        
        # 3. 读取网址文件
        url_file = 'urls.txt'
        if not os.path.exists(url_file):
            logging.error(f"找不到 {url_file} 文件，请检查是否已上传。")
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            logging.warning("urls.txt 是空的，没有需要访问的网址。")
            return

        # 4. 开始循环访问
        for index, url in enumerate(urls, 1):
            try:
                # 补全协议头
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                logging.info(f"[{index}/{len(urls)}] 正在访问: {url}")
                driver.get(url)
                
                # 在页面停留 5 秒确保加载
                time.sleep(5)
                logging.info(f"成功访问并停留: {url}")
                
            except InvalidArgumentException:
                logging.error(f"URL 格式错误，跳过: {url}")
            except Exception as e:
                logging.error(f"访问 {url} 时发生错误: {str(e)}")
                
    except Exception as e:
        logging.error(f"驱动初始化失败或程序崩溃: {str(e)}")
    finally:
        if driver:
            driver.quit()
            logging.info("浏览器已关闭。")
        
        # 5. 防止容器执行完立即退出导致 ClawCloud 报错 BackOff
        logging.info("所有任务已完成，进入待机状态保持容器在线...")
        while True:
            time.sleep(3600)

if __name__ == "__main__":
    run_automation()
