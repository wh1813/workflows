import os
import time
import logging
import random
import sys
import shutil
import traceback
import undetected_chromedriver as uc

# 1. 配置日志：确保日志能输出到 Docker 控制台
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def run_automation():
    print("-" * 50)
    logging.info(">>> 自动化程序启动")
    
    # [关键步骤] 清理缓存目录
    # Docker 中反复重启可能会导致用户目录锁定，强制清理以防报错
    data_dir = "/tmp/chrome_user_data"
    if os.path.exists(data_dir):
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
            logging.info("已清理旧的浏览器缓存目录")
        except Exception:
            pass

    # 2. 配置浏览器选项
    options = uc.ChromeOptions()
    
    # --- Docker 环境必须参数 ---
    options.add_argument("--headless=new")      # 新版无头模式 (防检测核心)
    options.add_argument("--no-sandbox")        # 必须：允许 root 运行
    options.add_argument("--disable-dev-shm-usage") # 必须：防止内存溢出
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-setuid-sandbox")
    
    # --- 伪装参数 ---
    options.add_argument("--window-size=1920,1080")
    # 指定数据目录到 /tmp，解决 Docker 权限问题
    options.add_argument(f"--user-data-dir={data_dir}")
    # 伪造 User-Agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    driver = None
    try:
        logging.info("正在启动 Undetected Chrome (首次运行需要下载驱动，请稍候)...")
        
        # 初始化浏览器
        # use_subprocess=True 在 Docker 中非常重要，防止进程僵死
        driver = uc.Chrome(
            options=options,
            version_main=None,  # 自动匹配版本
            use_subprocess=True,
            headless=True
        )
        
        logging.info(">>> 浏览器启动成功！")
        
        # 3. 读取网址文件
        url_file = 'urls.txt'
        if not os.path.exists(url_file):
            logging.error(f"错误: 根目录下找不到 {url_file} 文件")
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            logging.warning("urls.txt 内容为空")
            return

        # 4. 循环访问
        for index, url in enumerate(urls, 1):
            try:
                # 自动补全协议
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                
                logging.info(f"[{index}/{len(urls)}] 正在访问: {url}")
                
                # 访问页面
                driver.get(url)
                
                # --- 模拟真人浏览行为 ---
                
                # 初始加载等待
                time.sleep(random.uniform(3, 5))
                
                # 向下滚动 (触发 JS 统计)
                logging.info("    -> 模拟滚动...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(random.uniform(1, 2))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 最终停留
                wait_time = random.uniform(3, 6)
                logging.info(f"    -> 停留 {wait_time:.1f} 秒")
                time.sleep(wait_time)
                
                logging.info(f"    -> {url} 访问完成")
                
            except Exception as e:
                logging.error(f"访问 {url} 失败: {str(e)}")
                # 继续下一个，不中断程序
                continue

    except Exception as e:
        # 捕获浏览器启动级别的错误
        logging.error("!!! 浏览器初始化失败或严重崩溃 !!!")
        raise e  # 抛出异常以便主程序捕获打印堆栈

    finally:
        if driver:
            try:
                logging.info("关闭浏览器...")
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    try:
        run_automation()
        logging.info("所有任务执行完毕。")
    except Exception as e:
        print("\n" + "!"*50)
        print("!!! 程序发生未捕获异常 !!!")
        print("请截图以下错误信息进行调试：")
        traceback.print_exc()
        print("!"*50 + "\n")
