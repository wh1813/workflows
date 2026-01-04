import os
import time
import logging
import random
import undetected_chromedriver as uc # 引入防检测库

# 1. 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_automation():
    # 2. 配置 undetected-chromedriver
    options = uc.ChromeOptions()
    
    # 启用新版无头模式
    options.add_argument("--headless=new")
    
    # Docker 环境必须参数
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # 设置真实分辨率 (非常重要)
    options.add_argument("--window-size=1920,1080")
    
    # 这是一个比较通用的 Windows User-Agent，比 Linux 的更不容易被怀疑
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    driver = None
    try:
        logging.info("正在启动 Undetected Chrome...")
        
        # 【核心】：初始化 undetected_chromedriver
        # driver_executable_path=None 让库自动下载匹配的驱动
        # use_subprocess=True 在 Docker 中可以防止僵尸进程
        driver = uc.Chrome(
            options=options, 
            use_subprocess=True,
            version_main=None  # 自动检测 Chrome 版本
        )
        
        logging.info("Chrome 启动成功！")
        
        # 3. 读取网址
        url_file = 'urls.txt'
        if not os.path.exists(url_file):
            logging.error("找不到 urls.txt")
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        # 4. 循环访问
        for index, url in enumerate(urls, 1):
            try:
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                logging.info(f"[{index}/{len(urls)}] 访问: {url}")
                
                # 访问页面
                driver.get(url)
                
                # --- 模拟真人行为逻辑 ---
                
                # 随机停留 5-10 秒 (时间太短会被判定为无效访问)
                wait_time = random.uniform(5, 10)
                logging.info(f"停留 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
                
                # 必须滚动！很多统计代码只在滚动后触发
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/1.5);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                logging.info("访问完成")
                
            except Exception as e:
                logging.error(f"访问出错: {str(e)}")
                
    except Exception as e:
        logging.error(f"浏览器崩溃: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        logging.info("任务结束，进入待机...")
        while True:
            time.sleep(3600)

if __name__ == "__main__":
    run_automation()
