import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import InvalidArgumentException

# 1. 配置日志输出，方便在 ClawCloud 控制台查看运行状态
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_automation():
    # 2. 设置 Chrome 运行参数（针对 Docker 环境优化）
    chrome_options = Options()
    chrome_options.add_argument("--headless")           # 必须：云端无显示器环境
    chrome_options.add_argument("--no-sandbox")          # 必须：容器权限要求
    chrome_options.add_argument("--disable-dev-shm-usage") # 必须：防止内存溢出（使用 /tmp 替代共享内存）
    chrome_options.add_argument("--disable-gpu")         # 减少资源消耗
    
    # 额外优化：禁用图片加载，节省内存并加快速度
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    # 模拟真实浏览器 User-Agent，防止被简单反爬拦截
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        # 3. 自动安装并匹配对应的 ChromeDriver
        logging.info("正在初始化浏览器驱动...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("浏览器环境启动成功！")
        
        # 4. 读取网址文件
        url_file = 'urls.txt'
        if not os.path.exists(url_file):
            logging.error(f"找不到 {url_file} 文件，请检查是否已上传。")
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            logging.warning("urls.txt 是空的，没有需要访问的网址。")
            return

        # 5. 开始循环访问
        for index, url in enumerate(urls, 1):
            try:
                # 补全协议头
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                logging.info(f"[{index}/{len(urls)}] 正在访问: {url}")
                driver.get(url)
                
                # 等待 5 秒
                time.sleep(5)
                
                # 可选：保存截图到当前目录，证明访问成功（文件名包含时间戳）
                # driver.save_screenshot(f'visit_log_{index}.png')
                
            except InvalidArgumentException:
                logging.error(f"URL 格式错误，跳过: {url}")
            except Exception as e:
                logging.error(f"访问 {url} 时发生未知错误: {str(e)}")
                
    except Exception as e:
        logging.error(f"驱动初始化失败或程序崩溃: {str(e)}")
    finally:
        if driver:
            driver.quit()
            logging.info("浏览器已关闭，程序运行结束。")

if __name__ == "__main__":
    run_automation()
