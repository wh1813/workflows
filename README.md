# workflows
my-bot

loko219/web-bot:latest



PYTHONUNBUFFERED=1


可以计数的版本，后续可以基于此进行迭代
import os
import sys
import re
import io
import time
import json
import stat
import socket
import random
import shutil
import base64
import tarfile
import logging
import zipfile
import subprocess
import urllib.parse
import urllib.request
import concurrent.futures
from itertools import cycle
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ==================== 0. 核心目录配置 ====================
CONTAINER_DIR = "/home/container"
WORK_TMP_DIR = os.path.join(CONTAINER_DIR, "runtime_tmp")
BROWSER_ENV_DIR = os.path.join(CONTAINER_DIR, "lite_browser")
LIB_DIR = os.path.join(BROWSER_ENV_DIR, "lib_flat")

os.makedirs(WORK_TMP_DIR, exist_ok=True)
os.makedirs(BROWSER_ENV_DIR, exist_ok=True)
os.makedirs(LIB_DIR, exist_ok=True)

os.environ["TMPDIR"] = WORK_TMP_DIR
os.environ["TEMP"] = WORK_TMP_DIR
os.environ["TMP"] = WORK_TMP_DIR
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSER_ENV_DIR
os.environ["LD_LIBRARY_PATH"] = f"{LIB_DIR}:" + os.environ.get("LD_LIBRARY_PATH", "")
os.environ["PATH"] = f"{CONTAINER_DIR}:{BROWSER_ENV_DIR}:" + os.environ.get("PATH", "")

# ==================== 1. 核心运行参数配置 ====================
REMOTE_URLS_PATH = os.environ.get(
    "URLS_SOURCE",
    "https://raw.githubusercontent.com/wh1813/workflows/main/urls.txt"
)

SUBSCRIPTION_SOURCES = [
    "https://20261013-2hz.pages.dev/41955f55-55ec-4807-8715-715aef0aabdd/sub",
    "https://260902.tangtang.kdns.fr/4800de66-1f26-4f9e-8d82-42d1b3d9fd2c/sub?name=CFBox",
    "https://0824.hulu.kdns.fr/0e774815-c121-4c22-b5d8-b96820f46153/sub",
    "https://0823-3yi.pages.dev/sub?token=5d95ba6b79f9bccdecf0bd02c1825634",
    "https://edge-333a021d.pages.dev/bacf5764-28bd-4c84-9dc4-68cc90cbac8a/sub",
    "https://20260403.hulu.kdns.fr/sub?token=3388059324cd522abc3707b0559dda49"
]

# 打开网页之间的随机等待间隔（严格 6~10 秒）
INTERVAL_SECONDS_MIN = 6
INTERVAL_SECONDS_MAX = 10

# 节点定期轮换：每访问 5~8 个网页切换一次节点
NODE_SWITCH_MIN_URLS = 5
NODE_SWITCH_MAX_URLS = 8
SWITCH_PROXY_EACH_URL = False

# 极速发车：筛选出 15 个低延迟可用节点即立刻开始访问网页
MAX_VALID_NODES_POOL = 15
ROUND_INTERVAL = 10
FORCE_RECHECK_ROUNDS = 8

RAW_TCP_PRECHECK_TIMEOUT = 2.0
TCP_PRECHECK_WORKERS = 16
XRAY_VERSION_TAG = os.environ.get("XRAY_VERSION_TAG", "v1.8.24")

LOCAL_SOCKS_PORT = 10808
LOCAL_HTTP_PORT = 10809
XRAY_CONFIG_PATH = os.path.join(WORK_TMP_DIR, "xray_active_config.json")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


# ==================== 模块1: 依赖自愈与精简浏览器部署 ====================
def extract_deb_pure_python(deb_bytes, target_flat_lib_dir):
    if not deb_bytes.startswith(b"!<arch>\n"):
        return 0
    pos = 8
    extracted_count = 0
    while pos + 60 <= len(deb_bytes):
        header = deb_bytes[pos:pos + 60]
        name = header[0:16].decode("ascii", errors="ignore").strip().rstrip("/")
        size_str = header[48:58].decode("ascii", errors="ignore").strip()
        if not size_str.isdigit():
            break
        size = int(size_str)
        data_start = pos + 60
        data_end = data_start + size
        payload = deb_bytes[data_start:data_end]

        if name.startswith("data.tar"):
            try:
                with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as tar:
                    for member in tar.getmembers():
                        base_name = os.path.basename(member.name)
                        if ".so" in base_name:
                            dst_path = os.path.join(target_flat_lib_dir, base_name)
                            if member.isfile():
                                f_obj = tar.extractfile(member)
                                if f_obj:
                                    with open(dst_path, "wb") as out_f:
                                        out_f.write(f_obj.read())
                                    os.chmod(dst_path, 0o755)
                                    extracted_count += 1
                            elif member.issym() or member.islnk():
                                link_target_base = os.path.basename(member.linkname)
                                try:
                                    if os.path.lexists(dst_path):
                                        os.remove(dst_path)
                                    os.symlink(link_target_base, dst_path)
                                except Exception:
                                    pass
            except Exception:
                pass
        pos = data_end + (size % 2)
    return extracted_count


def resolve_and_download_missing_libs(binary_path):
    def _check_missing():
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:" + env.get("LD_LIBRARY_PATH", "")
        res = subprocess.run(["ldd", binary_path], capture_output=True, text=True, env=env)
        return [line.split("=>")[0].strip() for line in res.stdout.splitlines() if "not found" in line]

    missing = _check_missing()
    if not missing:
        logger.info("✅ [动态库自检] 精简浏览器所需的全部 Linux .so 库均已就绪！")
        return True

    logger.info("┌" + "─" * 58)
    logger.info(f"│ 🔧 [动态库自愈] 检测到缺失 {len(missing)} 个底层库，正在从 Debian 源补齐...")
    logger.info("└" + "─" * 58)

    required_pkgs = {
        "libnss3", "libnspr4", "libsqlite3-0", "libglib2.0-0", "libdbus-1-3",
        "libatk1.0-0", "libatk-bridge2.0-0", "libatspi2.0-0", "libcups2",
        "libdrm2", "libgbm1", "libxkbcommon0", "libxcomposite1", "libxdamage1",
        "libxfixes3", "libxrandr2", "libpango-1.0-0", "libpangocairo-1.0-0",
        "libcairo2", "libasound2", "libxcb1", "libx11-6", "libx11-xcb1",
        "libxext6", "libxi6", "libxtst6", "libexpat1", "libwayland-server0",
        "libwayland-client0", "libpciaccess0", "libxrender1", "libxshmfence1",
        "libpixman-1-0", "libfontconfig1", "libfreetype6", "libfribidi0",
        "libharfbuzz0b", "libthai0", "libdatrie1", "libgraphite2-3", "libpng16-16",
        "libavahi-common3", "libavahi-client3"
    }

    mirror_base = "http://deb.debian.org/debian"
    pkg_index_url = f"{mirror_base}/dists/bookworm/main/binary-amd64/Packages.xz"

    try:
        import lzma
        r = requests.get(pkg_index_url, timeout=20)
        index_text = lzma.decompress(r.content).decode("utf-8", errors="ignore")

        pkg_to_filename = {}
        current_pkg = None
        for line in index_text.splitlines():
            if line.startswith("Package: "):
                current_pkg = line[9:].strip()
            elif line.startswith("Filename: ") and current_pkg in required_pkgs:
                pkg_to_filename[current_pkg] = line[10:].strip()
                current_pkg = None

        def _dl_and_extract(item):
            _, rel_path = item
            try:
                resp = requests.get(f"{mirror_base}/{rel_path}", timeout=15)
                if resp.status_code == 200:
                    return extract_deb_pure_python(resp.content, LIB_DIR)
            except Exception:
                pass
            return 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_dl_and_extract, pkg_to_filename.items()))
        logger.info("   ✅ 动态链接库补齐解压完成！")
    except Exception as e:
        logger.warning(f"   ⚠️ 依赖库自动补齐部分跳过: {e}")
    return True


def ensure_lite_headless_browser():
    old_bad_dir = os.path.join(CONTAINER_DIR, " runtime_tmp")
    if os.path.exists(old_bad_dir):
        shutil.rmtree(old_bad_dir, ignore_errors=True)

    try:
        import playwright
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "--no-cache-dir", "-q"], check=False)

    def _find_real_binary():
        for root, _, files in os.walk(BROWSER_ENV_DIR):
            for f in files:
                if f in ("chrome-headless-shell", "headless_shell"):
                    p = os.path.join(root, f)
                    os.chmod(p, 0o755)
                    return p
        return None

    real_bin = _find_real_binary()
    if not real_bin:
        logger.info("🚀 正在下载精简版 chromium-headless-shell 内核...")
        res = subprocess.run([sys.executable, "-m", "playwright", "install", "--only-shell", "chromium"], env=os.environ)
        if res.returncode != 0:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], env=os.environ)
        real_bin = _find_real_binary()

    if not real_bin:
        raise RuntimeError("未能找到 chrome-headless-shell 二进制文件")

    resolve_and_download_missing_libs(real_bin)

    wrapper_path = os.path.join(BROWSER_ENV_DIR, "run_headless_wrapper.sh")
    wrapper_content = f"""#!/bin/sh
export LD_LIBRARY_PATH="{LIB_DIR}:$LD_LIBRARY_PATH"
exec "{real_bin}" "$@"
"""
    with open(wrapper_path, "w", encoding="utf-8") as f:
        f.write(wrapper_content)
    os.chmod(wrapper_path, 0o755)
    return wrapper_path


# ==================== 模块2: Xray 环境与订阅同步 ====================
def kill_stray_processes():
    subprocess.run("pkill -9 -f /home/container/xray", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -9 -f xray", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("pkill -9 -f chrome-headless-shell", shell=True, stderr=subprocess.DEVNULL)
    time.sleep(0.2)


def init_xray_env():
    kill_stray_processes()
    xray_bin = os.path.join(CONTAINER_DIR, "xray")
    need_download = not os.path.exists(xray_bin) and not shutil.which("xray")
    if not need_download and os.path.exists(xray_bin):
        try:
            res = subprocess.run([xray_bin, "version"], capture_output=True, text=True, timeout=5)
            line = res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""
            if XRAY_VERSION_TAG.lstrip("v") not in line:
                need_download = True
        except Exception:
            need_download = True

    if need_download:
        logger.info(f">>> [Xray准备] 正在下载部署 Xray ({XRAY_VERSION_TAG})...")
        tmp_zip = os.path.join(WORK_TMP_DIR, "xray_dl.zip")
        url = f"https://github.com/XTLS/Xray-core/releases/download/{XRAY_VERSION_TAG}/Xray-linux-64.zip"
        try:
            urllib.request.urlretrieve(url, tmp_zip)
        except Exception:
            url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
            urllib.request.urlretrieve(url, tmp_zip)

        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extract("xray", CONTAINER_DIR)
        os.chmod(xray_bin, 0o755)
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)
        logger.info("✅ [Xray准备] Xray 内核安装完毕。")


def sync_all_remote_resources():
    logger.info("┌" + "─" * 58)
    logger.info("│ 🌐 [远程同步] 正在并发拉取最新订阅节点与网址列表...")
    logger.info("└" + "─" * 58)

    all_links = []

    def _fetch_sub(url):
        links = []
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "v2rayN/6.23"})
            if r.status_code == 200 and r.text.strip():
                content = r.text.strip()
                if "://" not in content:
                    try:
                        content += "=" * ((4 - len(content) % 4) % 4)
                        content = base64.b64decode(content).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                for line in content.splitlines():
                    line = line.strip()
                    if line and "://" in line and not line.startswith("#"):
                        links.append(line)
        except Exception:
            pass
        return links

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for res in executor.map(_fetch_sub, SUBSCRIPTION_SOURCES):
            all_links.extend(res)

    unique_links = list(dict.fromkeys(all_links))
    if unique_links:
        with open("xray.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(unique_links) + "\n")
        logger.info(f"📥 [订阅汇总] 去重后保存 {len(unique_links)} 个节点至 xray.txt")

    if REMOTE_URLS_PATH:
        try:
            r = requests.get(REMOTE_URLS_PATH, timeout=10)
            if r.status_code == 200 and r.text.strip():
                with open("urls.txt", "w", encoding="utf-8") as f:
                    f.write(r.text.strip() + "\n")
                logger.info("✅ [网址同步] urls.txt 同步成功")
        except Exception as e:
            logger.warning(f"⚠️ urls.txt 远程同步失败: {e}")


# ==================== 模块3: 多线程极速预检与节点池管理 ====================
def raw_tcp_precheck(address, port, timeout=RAW_TCP_PRECHECK_TIMEOUT):
    t0 = time.time()
    try:
        with socket.create_connection((address, port), timeout=timeout):
            return True, int((time.time() - t0) * 1000)
    except Exception:
        return False, int((time.time() - t0) * 1000)


def wait_port_open_or_dead(host, port, process, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False, True
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True, False
        except Exception:
            time.sleep(0.1)
    return False, (process.poll() is not None)


class XrayProxyManager:
    def __init__(self, xray_file="xray.txt"):
        self.xray_file = xray_file
        self.process = None
        self.last_nodes_set = set()
        self.valid_nodes = []
        self.node_cycle = None
        self.current_node = None

    def _read_links_from_file(self):
        if not os.path.exists(self.xray_file):
            return []
        with open(self.xray_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        if len(lines) == 1 and "://" not in lines[0]:
            try:
                raw = lines[0] + "=" * ((4 - len(lines[0]) % 4) % 4)
                decoded = base64.b64decode(raw).decode("utf-8", errors="ignore")
                lines = [l.strip() for l in decoded.splitlines() if l.strip() and not l.strip().startswith("#")]
            except Exception:
                pass
        return list(dict.fromkeys(lines))

    def _parse_node_to_outbound(self, link):
        if link.startswith("vmess://"):
            b64 = link[8:].split("#")[0]
            b64 += "=" * ((4 - len(b64) % 4) % 4)
            conf = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
            address = conf.get("add")
            port = int(conf.get("port", 443))
            uid = conf.get("id")
            net = conf.get("net", "tcp")
            tls = conf.get("tls", "")
            host = conf.get("host", "") or conf.get("sni", "") or address
            path = conf.get("path", "/")
            stream = {"network": net}
            if tls == "tls":
                stream["security"] = "tls"
                stream["tlsSettings"] = {
                    "serverName": host,
                    "allowInsecure": True,
                    "fingerprint": "chrome",
                    "alpn": ["http/1.1"]
                }
            if net == "ws":
                stream["wsSettings"] = {"path": path, "headers": {"Host": host}}
            outbound = {
                "protocol": "vmess",
                "settings": {"vnext": [{"address": address, "port": port, "users": [{"id": uid, "alterId": int(conf.get("aid", 0)), "security": "auto"}]}]},
                "streamSettings": stream
            }
            return outbound, address, port, "vmess"

        elif link.startswith(("vless://", "trojan://")):
            parsed = urllib.parse.urlparse(link)
            protocol = parsed.scheme
            uid_or_pwd = urllib.parse.unquote(parsed.username or "")
            address = parsed.hostname
            port = int(parsed.port or 443)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            net = params.get("type", "tcp")
            security = params.get("security", "tls" if (protocol == "trojan" or port in [443, 8443, 2053, 2083, 2087, 2096]) else "none")
            sni = params.get("sni") or params.get("host") or ""
            host = params.get("host") or params.get("sni") or ""
            path = params.get("path", "/")
            flow = params.get("flow", "").strip()
            user_entry = {"id": uid_or_pwd, "encryption": "none"}
            if flow:
                user_entry["flow"] = flow
            if protocol == "vless":
                settings = {"vnext": [{"address": address, "port": port, "users": [user_entry]}]}
            else:
                settings = {"servers": [{"address": address, "port": port, "password": uid_or_pwd}]}
            stream = {"network": net}
            if security == "tls":
                stream["security"] = "tls"
                tls_settings = {
                    "serverName": sni if sni else (host if host else address),
                    "allowInsecure": True,
                    "fingerprint": params.get("fp", "chrome") or "chrome"
                }
                alpn_val = params.get("alpn", "")
                if alpn_val:
                    tls_settings["alpn"] = alpn_val.split(",")
                stream["tlsSettings"] = tls_settings
            elif security == "reality":
                stream["security"] = "reality"
                stream["realitySettings"] = {
                    "serverName": sni if sni else address,
                    "fingerprint": "chrome",
                    "publicKey": params.get("pbk", "").strip(),
                    "shortId": params.get("sid", "").strip()
                }
            else:
                stream["security"] = "none"
            if net == "ws":
                ws_settings = {"path": path}
                if host:
                    ws_settings["headers"] = {"Host": host}
                stream["wsSettings"] = ws_settings
            elif net == "grpc":
                stream["grpcSettings"] = {"serviceName": params.get("serviceName", "")}
            return {"protocol": protocol, "settings": settings, "streamSettings": stream}, address, port, protocol

        elif link.startswith("ss://"):
            body = link[5:].split("#")[0]
            if "@" in body:
                userinfo, hostport = body.split("@", 1)
                if ":" not in userinfo:
                    userinfo += "=" * ((4 - len(userinfo) % 4) % 4)
                    userinfo = base64.b64decode(userinfo).decode("utf-8", errors="ignore")
                method, password = userinfo.split(":", 1)
            else:
                body += "=" * ((4 - len(body) % 4) % 4)
                decoded = base64.b64decode(body).decode("utf-8", errors="ignore")
                userinfo, hostport = decoded.rsplit("@", 1)
                method, password = userinfo.split(":", 1)
            address, port = hostport.split(":", 1)
            port = int(port.split("/")[0].split("?")[0])
            outbound = {
                "protocol": "shadowsocks",
                "settings": {"servers": [{"address": address, "port": port, "method": method, "password": urllib.parse.unquote(password)}]}
            }
            return outbound, address, port, "shadowsocks"
        raise ValueError("不支持的节点协议")

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                    self.process.wait(timeout=1.0)
                except Exception:
                    pass
            self.process = None
        subprocess.run("pkill -9 -f xray", shell=True, stderr=subprocess.DEVNULL)

    def _start_xray_and_probe(self, outbound):
        config = {
            "log": {"loglevel": "none"},
            "inbounds": [
                {"port": LOCAL_SOCKS_PORT, "listen": "127.0.0.1", "protocol": "socks", "settings": {"udp": True}},
                {"port": LOCAL_HTTP_PORT, "listen": "127.0.0.1", "protocol": "http"}
            ],
            "outbounds": [outbound]
        }
        with open(XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        self.stop()
        xray_bin = "/home/container/xray" if os.path.exists("/home/container/xray") else "xray"
        start_t = time.time()
        try:
            self.process = subprocess.Popen(
                [xray_bin, "run", "-c", XRAY_CONFIG_PATH],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
            port_ready, process_dead = wait_port_open_or_dead("127.0.0.1", LOCAL_HTTP_PORT, self.process, timeout=2.5)
            if process_dead or not port_ready:
                self.stop()
                return False, int((time.time() - start_t) * 1000)

            proxies = {
                "http": f"http://127.0.0.1:{LOCAL_HTTP_PORT}",
                "https": f"http://127.0.0.1:{LOCAL_HTTP_PORT}"
            }
            headers = {"User-Agent": USER_AGENTS[0]}

            # 严苛探针：必须同时能顺利访问 Book118 与 百度统计域名，才算有效节点！
            try:
                r1 = requests.get("https://max.book118.com/robots.txt", proxies=proxies, headers=headers, timeout=4.0, verify=False)
                if r1.status_code in (200, 301, 302, 403):
                    return True, int((time.time() - start_t) * 1000)
            except Exception:
                pass

            self.stop()
            return False, int((time.time() - start_t) * 1000)
        except Exception:
            self.stop()
            return False, int((time.time() - start_t) * 1000)

    def _filter_links_two_stage(self, links_to_test, max_needed=MAX_VALID_NODES_POOL):
        if not links_to_test:
            return []

        parsed_list = []
        for link in links_to_test:
            try:
                outbound, addr, port, proto = self._parse_node_to_outbound(link)
                if outbound and addr:
                    parsed_list.append({
                        "link": link, "outbound": outbound,
                        "addr": addr, "port": port, "proto": proto,
                        "tag": f"{addr}:{port}({proto})"
                    })
            except Exception:
                pass

        tcp_passed = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=TCP_PRECHECK_WORKERS) as executor:
            future_map = {executor.submit(raw_tcp_precheck, item["addr"], item["port"]): item for item in parsed_list}
            for future in concurrent.futures.as_completed(future_map):
                item = future_map[future]
                try:
                    ok, tcp_ms = future.result()
                    if ok:
                        item["tcp_ms"] = tcp_ms
                        tcp_passed.append(item)
                except Exception:
                    pass

        tcp_passed.sort(key=lambda x: x.get("tcp_ms", 9999))
        logger.info(f"✅ [TCP极速预筛] 存活 {len(tcp_passed)} 个节点，开始筛选前 {max_needed} 个直通 Book118 的节点...")

        passed_nodes = []
        for item in tcp_passed:
            ok, cost_ms = self._start_xray_and_probe(item["outbound"])
            if ok:
                item["proxy_ms"] = cost_ms
                passed_nodes.append(item)
                logger.info(f"   ✅ [{len(passed_nodes)}/{max_needed}] 节点有效 -> {item['tag']} | {cost_ms}ms")
                if len(passed_nodes) >= max_needed:
                    break
            else:
                logger.info(f"   ❌ {item['tag']} 无法直通Book118(已剔除)")

        return passed_nodes

    def check_and_reload_nodes(self, force_full_recheck=False):
        current_links = self._read_links_from_file()
        current_set = set(current_links)
        if not current_links:
            self.stop()
            self.current_node = None
            return False

        if force_full_recheck or not self.valid_nodes:
            self.valid_nodes = self._filter_links_two_stage(current_links, max_needed=MAX_VALID_NODES_POOL)
            self.last_nodes_set = current_set
            if not self.valid_nodes:
                self.stop()
                return False
            random.shuffle(self.valid_nodes)
            self.node_cycle = cycle(self.valid_nodes)
            return self.switch_to_next_valid_node()

        added_links = list(current_set - self.last_nodes_set)
        removed_links = self.last_nodes_set - current_set
        if added_links or removed_links:
            logger.info(f"🆕 [节点更新] 检测到 xray.txt 变化 (新增:{len(added_links)}, 移除:{len(removed_links)})")
            self.last_nodes_set = current_set
            if removed_links:
                self.valid_nodes = [n for n in self.valid_nodes if n["link"] not in removed_links]
            if added_links:
                new_ok = self._filter_links_two_stage(added_links, max_needed=10)
                if new_ok:
                    self.valid_nodes.extend(new_ok)
            if not self.valid_nodes:
                return False
            random.shuffle(self.valid_nodes)
            self.node_cycle = cycle(self.valid_nodes)
            return self.switch_to_next_valid_node()

        logger.info(f"✅ [节点复用] xray.txt 无变化，继续使用当前可用池 ({len(self.valid_nodes)} 个可用)")
        if not self.process or self.process.poll() is not None:
            return self.switch_to_next_valid_node()
        return True

    def switch_to_next_valid_node(self):
        if not self.valid_nodes:
            self.stop()
            self.current_node = None
            return False
        attempts = len(self.valid_nodes)
        for _ in range(attempts):
            candidate = next(self.node_cycle)
            if self.current_node and len(self.valid_nodes) > 1 and candidate["link"] == self.current_node["link"]:
                candidate = next(self.node_cycle)
            ok, cost_ms = self._start_xray_and_probe(candidate["outbound"])
            if ok:
                self.current_node = candidate
                logger.info(f"🎉 [节点已激活] 当前出口 -> {candidate['tag']} | 延迟: {cost_ms}ms")
                return True
            else:
                self.valid_nodes = [n for n in self.valid_nodes if n["link"] != candidate["link"]]
                if not self.valid_nodes:
                    break
                self.node_cycle = cycle(self.valid_nodes)
        self.stop()
        self.current_node = None
        return False


# ==================== 模块4: URL 管理 ====================
class URLManager:
    def __init__(self, urls_file="urls.txt"):
        self.urls_file = urls_file
        self.last_urls = []

    def check_and_get_urls(self):
        if not os.path.exists(self.urls_file):
            return []
        with open(self.urls_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        cleaned = [u if u.startswith(("http://", "https://")) else "https://" + u for u in urls]
        if not self.last_urls:
            logger.info(f"📋 [队列加载] 共加载 {len(cleaned)} 个目标网页")
        elif cleaned != self.last_urls:
            logger.info(f"🆕 [队列更新] 检测到 urls.txt 变化，更新至 {len(cleaned)} 个网页")
        else:
            logger.info(f"✅ [队列检查] urls.txt 无变化，共 {len(cleaned)} 个网页")
        self.last_urls = cleaned
        return cleaned


# ==================== 模块5: 真正计入浏览量的精简浏览器控制器 ====================
class LiteHeadlessBrowser:
    def __init__(self, wrapper_bin, use_proxy=True):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.use_proxy = use_proxy
        self.stat_hits = 0

        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--no-first-run",
            "--single-process",
            "--renderer-process-limit=1",
            "--in-process-gpu",
            "--js-flags=--max-old-space-size=64 --expose-gc",
            "--disk-cache-size=1",
            "--media-cache-size=1",
            "--aggressive-cache-discard",
            "--disable-site-isolation-trials",
            "--ignore-certificate-errors",
            "--disable-blink-features=AutomationControlled",
        ]

        proxy_cfg = {"server": f"http://127.0.0.1:{LOCAL_HTTP_PORT}"} if use_proxy else None

        launch_env = os.environ.copy()
        launch_env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:" + launch_env.get("LD_LIBRARY_PATH", "")
        launch_env["MALLOC_ARENA_MAX"] = "2"

        self.browser = self.pw.chromium.launch(
            executable_path=wrapper_bin,
            headless=True,
            args=launch_args,
            proxy=proxy_cfg,
            env=launch_env
        )
        self._recreate_context()

    def _recreate_context(self):
        self.ua = random.choice(USER_AGENTS)
        # 【关键修复1】：绝不设置全局 extra_http_headers 的 Referer！
        # 否则页面内部发出的所有 XHR/Ajax 计数请求的 Referer 都会被篡改成 baidu.com 从而被后端防盗链拒绝！
        self.context = self.browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=self.ua,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            ignore_https_errors=True
        )
        # 深度伪造真实桌面 Chrome 指纹，绕过前端统计 JS 的无头检测
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };
        """)
        self.page = self.context.new_page()

        # 【关键修复2】：绝对不能拦截 stylesheet (CSS)！
        # 拦截 CSS 会导致页面元素高度为 0、预览区无法触发可视曝光事件，现仅拦截音视频和超大字体包
        self.page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("media", "font")
            else route.continue_()
        )

        # 实时监听页面发出的真实统计与浏览量计数请求，验证浏览量是否真正上报成功
        def _on_response(response):
            u = response.url.lower()
            if any(k in u for k in ["hm.baidu.com/hm.gif", "viewcount", "viewurl", "getpreview", "stat", "count", "click", "ajax", "cnzz", "51.la"]):
                if response.status in (200, 204, 302):
                    self.stat_hits += 1

        self.page.on("response", _on_response)

    def visit_and_interact(self, url):
        t0 = time.time()
        self.stat_hits = 0
        try:
            # 仅在打开主文档页面的第一跳传入百度搜索 Referer，后续内部 JS 请求自动携带当前文档 URL 作为 Referer
            resp = self.page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=22000,
                referer="https://www.baidu.com/link?url=KkKS_fake_search_result"
            )
            status = resp.status if resp else 200
            load_ms = int((time.time() - t0) * 1000)

            # 等待外部统计 JS 文件加载并执行初始化
            try:
                self.page.wait_for_load_state("load", timeout=8000)
            except Exception:
                pass

            title = self.page.title() or "文档详情"

            if status == 403 or "403 forbidden" in title.lower():
                logger.info(f"    ℹ️ [页面已删除/403] 状态码:{status} | {load_ms}ms | 标题:《{title[:28]}》")
                return True
            else:
                logger.info(f"    ✅ [浏览器打开成功] 状态码:{status} | {load_ms}ms | 标题:《{title[:28]}》")

            # 1. 初次停留 3~5 秒，等待首屏统计脚本执行
            w1 = random.uniform(3.0, 5.0)
            self.page.wait_for_timeout(int(w1 * 1000))

            # 2. 模拟真人鼠标移动与分步滚动（触发懒加载与曝光计数监听器）
            try:
                self.page.mouse.move(random.randint(200, 600), random.randint(200, 500))
                self.page.mouse.wheel(0, 400)
                self.page.evaluate("window.scrollTo({top: document.body.scrollHeight / 3, behavior: 'smooth'});")
            except Exception:
                pass
            w2 = random.uniform(2.5, 4.0)
            self.page.wait_for_timeout(int(w2 * 1000))

            # 3. 尝试点击“继续阅读 / 展开全文”按钮
            try:
                btn = self.page.query_selector(".more-btn, .read-more, .banner-more-btn, #moreBtn, div.fc2e, #btn_read_more")
                if btn:
                    btn.scroll_into_view_if_needed()
                    self.page.wait_for_timeout(600)
                    btn.click(force=True)
                    logger.info("    🖱️ 触发【继续阅读/展开】点击成功")
                    self.page.wait_for_timeout(2000)
            except Exception:
                pass

            # 4. 滚动到底部并等待所有网络统计请求收尾
            try:
                self.page.mouse.wheel(0, 600)
                self.page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
            except Exception:
                pass
            w3 = random.uniform(4.5, 7.0)
            self.page.wait_for_timeout(int(w3 * 1000))

            total_stay = w1 + w2 + w3
            logger.info(
                f"    📡 [真实浏览完成] 捕获有效统计/计数响应: {self.stat_hits} 个 | 总停留 {total_stay:.1f}s"
            )
            return True
        finally:
            try:
                self.page.goto("about:blank", timeout=3000)
                self.page.evaluate("if (window.gc) window.gc();")
            except Exception:
                pass

    def close(self):
        for obj in (getattr(self, "page", None), getattr(self, "context", None), getattr(self, "browser", None)):
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
        if getattr(self, "pw", None):
            try:
                self.pw.stop()
            except Exception:
                pass
        subprocess.run("pkill -9 -f chrome-headless-shell", shell=True, stderr=subprocess.DEVNULL)
        for fn in os.listdir(WORK_TMP_DIR):
            if fn.startswith("playwright_"):
                shutil.rmtree(os.path.join(WORK_TMP_DIR, fn), ignore_errors=True)


# ==================== 模块6: 主循环 ====================
def main():
    init_xray_env()
    wrapper_bin = ensure_lite_headless_browser()

    proxy_mgr = XrayProxyManager("xray.txt")
    url_mgr = URLManager("urls.txt")

    round_num = 1
    urls_since_last_switch = 0
    next_switch_threshold = random.randint(NODE_SWITCH_MIN_URLS, NODE_SWITCH_MAX_URLS)

    while True:
        browser = None
        try:
            logger.info("\n" + "#" * 60)
            logger.info(f"🔄 [第 {round_num} 轮] 重新读取检查 xray.txt 与 urls.txt 是否有更新...")
            logger.info("#" * 60)

            sync_all_remote_resources()
            valid_urls = url_mgr.check_and_get_urls()
            if not valid_urls:
                logger.warning("⚠️ urls.txt 为空，休眠 30 秒后重试...")
                time.sleep(30)
                continue

            force_full = (round_num > 1 and (round_num - 1) % FORCE_RECHECK_ROUNDS == 0)
            has_proxy = proxy_mgr.check_and_reload_nodes(force_full_recheck=force_full)

            logger.info("🌐 正在拉起【精简版无头浏览器 (Chromium Headless Shell)】...")
            browser = LiteHeadlessBrowser(wrapper_bin=wrapper_bin, use_proxy=has_proxy)
            logger.info("✅ 精简版无头浏览器启动成功！")

            logger.info("\n" + "=" * 60)
            logger.info(f"🚀 [开始巡检] 第 {round_num} 轮 | 网页总数: {len(valid_urls)} | 可用节点池: {len(proxy_mgr.valid_nodes)}")
            logger.info(f"ℹ️ 网页随机间隔: {INTERVAL_SECONDS_MIN}~{INTERVAL_SECONDS_MAX}s | 换节点阈值: 每 {NODE_SWITCH_MIN_URLS}~{NODE_SWITCH_MAX_URLS} 个网页")
            logger.info("=" * 60)

            for index, url in enumerate(valid_urls, start=1):
                need_switch = False
                if has_proxy and len(proxy_mgr.valid_nodes) > 0:
                    if SWITCH_PROXY_EACH_URL and index > 1:
                        need_switch = True
                    elif urls_since_last_switch >= next_switch_threshold:
                        logger.info(f"\n🔁 [定期轮换] 已连续访问 {urls_since_last_switch} 个网页，切换下一个可用节点并重置浏览器...")
                        need_switch = True

                if need_switch:
                    browser.close()
                    has_proxy = proxy_mgr.switch_to_next_valid_node()
                    browser = LiteHeadlessBrowser(wrapper_bin=wrapper_bin, use_proxy=has_proxy)
                    urls_since_last_switch = 0
                    next_switch_threshold = random.randint(NODE_SWITCH_MIN_URLS, NODE_SWITCH_MAX_URLS)
                    logger.info(f"ℹ️ [下次轮换] 访问 {next_switch_threshold} 个网页后再次切换节点")

                node_label = proxy_mgr.current_node["tag"] if (has_proxy and proxy_mgr.current_node) else "直连模式"
                logger.info(f"\n[{index}/{len(valid_urls)}] 节点: {node_label} | 正在访问: {url}")

                try:
                    browser.visit_and_interact(url)
                    urls_since_last_switch += 1
                except Exception as e:
                    err_str = str(e)
                    logger.error(f"    -> 页面访问异常: {err_str}")
                    if any(kw in err_str for kw in ["ERR_SSL", "ERR_TIMED_OUT", "ERR_CONNECTION", "Timeout"]):
                        logger.warning(">>> 检测到节点底层 TLS 握手异常或严重超时，立即切换下一个节点...")
                        browser.close()
                        has_proxy = proxy_mgr.switch_to_next_valid_node()
                        browser = LiteHeadlessBrowser(wrapper_bin=wrapper_bin, use_proxy=has_proxy)
                        urls_since_last_switch = 0

                if index < len(valid_urls):
                    wait_sec = random.uniform(INTERVAL_SECONDS_MIN, INTERVAL_SECONDS_MAX)
                    logger.info(f"⏳ [网页间隔] 随机等待 {wait_sec:.1f} 秒...")
                    time.sleep(wait_sec)

            logger.info("\n" + "~" * 60)
            logger.info(f"✨ [本轮完成] 第 {round_num} 轮全部 {len(valid_urls)} 个网页已访问完毕！")
            logger.info(f"💤 休息 {ROUND_INTERVAL} 秒后，将重新读取 xray.txt 与 urls.txt 开启第 {round_num + 1} 轮...")
            logger.info("~" * 60)

            round_num += 1
            time.sleep(ROUND_INTERVAL)

        except Exception as e:
            logger.error(f"⚠️ [主循环异常] {e}，10 秒后自动恢复...")
            time.sleep(10)
        finally:
            if browser:
                browser.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("程序已手动停止。")
