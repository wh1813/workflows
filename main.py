import os
import time
import logging
import random
import sys
import shutil
import undetected_chromedriver as uc

# 1. 配置日志：强制输出到标准输出 (stdout)，解决 Docker 看不到日志的问题
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def run_automation():
    # 清理旧的缓存目录（如果存在），防止占用空间或权限错误
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir, ignore_errors=True)

    # 2. 配置 undetected_chromedriver
    options = uc.ChromeOptions()
    
    # 【关键】新版无头模式，必须由 uc 库处理
    # 注意：在 uc.Chrome() 初始化时会再次确认 headless 参数，这里添加是双重保险
    options.add_argument("--headless=new")
    
    # Docker 必须参数
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-setuid-sandbox")
    
    # 设置分辨率 (伪装成普通显示器)
    options.add_argument("--window-size=1920,1080")
    
    # 设置用户目录到 /tmp，避免在 /app 目录下出现权限问题
    options.add_argument(f"--user-data-dir={data_dir}")
    
    # 随机 User-Agent (这是 Windows 10 Chrome 的 UA，伪装性好)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        logging.info(">>> 正在启动 Undetected Chrome (这可能需要几秒钟)...")
        
        # 【核心初始化】
        # version_main=None: 让库自动寻找安装好的 Chrome 版本
        # use_subprocess=True: 必须开启，防止 Docker 中进程死锁
        driver = uc.Chrome(
            options=options,
            version_main=None,
            use_subprocess=True,
            headless=True # 在这里显式指定 headless
        )
        
        logging.info(">>> 浏览器启动成功！")
        
        # 3. 读取网址
        url_file = 'urls.txt'
        if not os.path.exists(url_file):
            logging.error(f"错误: 找不到 {url_file} 文件")
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            logging.warning("警告: urls.txt 是空的")
            return

        # 4. 循环访问逻辑
        for index, url in enumerate(urls, 1):
            try:
                # 补全 URL
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                logging.info(f"[{index}/{len(urls)}] 正在访问: {url}")
                
                # 打开网页
                driver.get(url)
                
                # --- 行为模拟 (欺骗统计代码) ---
                
                # 1. 初始加载等待
                time.sleep(random.uniform(3, 5))
                
                # 2. 模拟向下滚动 (触发懒加载和统计 JS)
                logging.info("    -> 模拟鼠标滚动...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(random.uniform(1, 2))
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/1.5);")
                time.sleep(random.uniform(1, 2))
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 3. 最后停留
                wait_time = random.uniform(2, 4)
                logging.info(f"    -> 停留 {wait_time:.1f} 秒")
                time.sleep(wait_time)
                
            except Exception as e:
                logging.error(f"访问 {url} 时出错: {str(e)}")
                # 如果浏览器挂了，尝试重启或者跳过
                continue

    except Exception as e:
        logging.error(f"!!! 致命错误: {str(e)}")
        # 打印详细堆栈以便调试
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            try:
                logging.info("正在关闭浏览器...")
                driver.quit()
            except:
                pass
        
        # 5. 保活逻辑 (防止容器退出导致看不到日志)
        logging.info("所有任务已结束。容器进入待机模式 (便于查看日志)...")
        while True:
            time.sleep(3600)

if __name__ == "__main__":
    run_automation()
