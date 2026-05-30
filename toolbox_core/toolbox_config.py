import os, sys, argparse, json, hashlib, base64

parser = argparse.ArgumentParser()
parser.add_argument("--dir", type=str, default=None,
                   help="Base directory for output files")
args = parser.parse_args()

# ── 路径配置 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 如果传入了 --dir 参数，覆盖默认路径
if args.dir and os.path.isdir(args.dir):
    SCRIPT_DIR = args.dir

def _get_config_dir():
    if getattr(sys, 'frozen', False):
        d = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'planning-toolbox')
        os.makedirs(d, exist_ok=True)
        return d
    return SCRIPT_DIR


def _ensure_frozen_config():
    """用打包内置的完整配置覆盖 APPDATA 配置，仅保留 API Key（如有）"""
    if not getattr(sys, 'frozen', False):
        return
    cfg_path = CONFIG_FILE
    internal_cfg = os.path.join(SCRIPT_DIR, "toolbox_core", "svn_gui_config.json")
    alt_internal = os.path.join(os.path.dirname(SCRIPT_DIR), "toolbox_core", "svn_gui_config.json")
    src = None
    for p in (internal_cfg, alt_internal):
        if os.path.isfile(p):
            src = p
            break
    if not src:
        return
    with open(src, "r", encoding="utf-8") as f:
        src_cfg = json.load(f)
    src_cfg.pop("tr_api_key", None)
    src_cfg.pop("tr_api_key_enc", None)
    if not os.path.isfile(cfg_path):
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(src_cfg, f, ensure_ascii=False, indent=2)
        return
    with open(cfg_path, "r", encoding="utf-8") as f:
        dst_cfg = json.load(f)
    for k, v in src_cfg.items():
        if k not in dst_cfg:
            dst_cfg[k] = v
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(dst_cfg, f, ensure_ascii=False, indent=2)

MAIN_SCRIPT = os.path.join(SCRIPT_DIR, "svn_oneclick_compare.py")
CONFIG_FILE = os.path.join(_get_config_dir(), "svn_gui_config.json")
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "输出")  # GUI 同级输出文件夹

# ── API Key 加密 ─────────────────────────────────────────
def _obfuscation_key():
    """固定混淆密钥，确保配置在任意机器上都能解密。阻止直接文本窥探，不阻止逆向"""
    return hashlib.sha256(b"CeHuaToolBox_Obfs_Key_v1").digest()

def encrypt_key(plaintext):
    """混淆加密 API Key，返回 base64 字符串"""
    if not plaintext:
        return ""
    key = _obfuscation_key()
    data = plaintext.encode("utf-8")
    encrypted = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
    return base64.b64encode(encrypted).decode("ascii")

def decrypt_key(ciphertext):
    """解密 API Key，返回原文。失败返回空字符串"""
    if not ciphertext:
        return ""
    try:
        key = _obfuscation_key()
        encrypted = base64.b64decode(ciphertext.encode("ascii"))
        decrypted = bytes(encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted)))
        return decrypted.decode("utf-8")
    except Exception:
        return ""

# ── 配置读写 ──────────────────────────────────────────────
def load_config():
    default = {
        "svn_urls": [
            "http://192.168.1.41:8080/svn/D3/branches/20240606_KR2/gameData/Text/Texts.xlsm"
        ],
        "svn_url_mappings": {},
        "cmp_file_presets": []
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 合并默认值
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                # 自动解密 API Key（混淆存储，防窥探）
                enc = data.pop("tr_api_key_enc", "")
                if enc:
                    data["tr_api_key"] = decrypt_key(enc)
                return data
        except json.JSONDecodeError:
            print("⚠️ 配置文件损坏，使用默认配置")
            return default
        except Exception as e:
            print(f"⚠️ 加载配置失败: {e}")
            return default
    return default

def save_config(config):
    try:
        data = dict(config)
        # 自动加密 API Key，不写入明文
        plain = data.pop("tr_api_key", "")
        if plain:
            data["tr_api_key_enc"] = encrypt_key(plain)
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存配置失败: {e}")

def int_or(val, default):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default
