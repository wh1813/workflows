import os
import time
import logging
import random
import sys
import shutil
import traceback
import undetected_chromedriver as uc

# 1. 配置日志：强制输出到标准输出 (stdout)，确保 Docker 能抓取到日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def run_automation():
    print(">>> [步骤1] 正在清理缓存环境...")
    # 清理旧的缓存目录，防止权限冲突
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir, ignore_errors=True)

    # 2. 配置 undetected_chromedriver
    print(">>> [步骤2] 配置 Chrome 选项...")
    options = uc.ChromeOptions()
    
    # 【核心伪装】：启用新版无头模式
    options.add_argument("--headless=new")
    
    # Docker 环境必须参数
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-setuid-sandbox")
    
    # 伪装分辨率
    options.add_argument("--window-size=1920,1080")
    
    # 指定用户目录到 /tmp (解决 Docker 权限报错的关键)
    options.add_argument(f"--user-data-dir={data_dir}")
    
    # 设置 Windows User-Agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    driver = None
    try:
        print(">>> [步骤3] 正在启动浏览器 (Undetected Chrome)...")
        logging.info("初始化驱动中，这可能需要几十秒下载驱动...")
        
        # 【驱动初始化】
        # use_subprocess=True: 必须开启，防止 Docker 僵尸进程
        # version_main=None: 自动匹配版本
        driver = uc.Chrome(
            options=options,
            version_main=None,
            use_subprocess=True,
            headless=True
        )
        
        logging.info(">>> 浏览器启动成功！开始处理任务...")
        
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

        # 4. 循环访问
        for index, url in enumerate(urls, 1):
            try:
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                logging.info(f"[{index}/{len(urls)}] 正在访问: {url}")
                
                # 打开网页
                driver.get(url)
                
                # --- 模拟真人行为 (欺骗统计代码) ---
                
                # 随机停留等待加载
                sleep_time = random.uniform(3, 6)
                logging.info(f"    -> 页面加载中，等待 {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                
                # 模拟滚动 (触发懒加载)
                logging.info("    -> 模拟滚动...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(random.uniform(1, 2))
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/1.2);")
                time.sleep(random.uniform(1, 2))
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 最后的阅读停留
                logging.info("    -> 停留浏览中...")
                time.sleep(random.uniform(2, 4))
                
                logging.info(f"    -> 访问完成: {url}")
                
            except Exception as e:
                logging.error(f"访问单条 URL 出错: {str(e)}")
                continue

    except Exception as e:
        # 这里只抛出异常，交给主函数处理打印
        raise e
        
    finally:
        if driver:
            try:
                logging.info("正在关闭浏览器...")
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    print("="*50)
    print(">>> 容器主程序启动")
    print("="*50)
    
    try:
        run_automation()
        print("\n>>> 所有任务正常完成。")
        
    except Exception as e:
        print("\n" + "!"*50)
        print("!!! 程序运行期间发生崩溃 !!!")
        print("错误详情如下 (请截图):")
        print("-" * 30)
        # 打印完整的错误堆栈，方便排查
        traceback.print_exc()
        print("-" * 30)
        print("!"*50 + "\n")
        
    finally:
        # 【核心保活逻辑】
        # 无论成功还是失败，都进入死循环，防止 Pod 变为 Terminated
        print(">>> 容器进入【无限待机模式】以保持 Logs 可见。")
        print(">>> 你现在可以在控制台查看上方的报错信息了。")
        while True:
            time.sleep(3600)
