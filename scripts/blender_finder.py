"""
blender_finder.py
自动扫描与探测 Windows 环境下的 Blender 可执行文件路径
全程动态探测：无任何硬编码绝对路径或盘符，自适应不同系统与 Steam 库分布。
"""

import os
import sys
import glob
import shutil
import json
import winreg
import string

def get_env_blender():
    """检查环境变量 BLENDER_PATH"""
    env_path = os.environ.get("BLENDER_PATH")
    if env_path and os.path.isfile(env_path) and env_path.lower().endswith("blender.exe"):
        return os.path.abspath(env_path)
    return None

def get_path_blender():
    """检查系统环境变量 PATH 中的 blender 命令"""
    which_path = shutil.which("blender")
    if which_path:
        return os.path.abspath(which_path)
    return None

def get_registry_blender():
    """通过 Windows 注册表关联与安装项动态检索"""
    reg_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes\blendfile\shell\open\command"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\blendfile\shell\open\command"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes\Applications\blender.exe\shell\open\command"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\blender.exe\shell\open\command"),
    ]
    for root, subkey in reg_keys:
        try:
            with winreg.OpenKey(root, subkey) as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val:
                    val = val.strip()
                    if val.startswith('"'):
                        candidate = val.split('"')[1]
                    else:
                        candidate = val.split()[0]
                    if os.path.isfile(candidate) and candidate.lower().endswith("blender.exe"):
                        return os.path.abspath(candidate)
        except Exception:
            continue
    return None

def get_steam_libraries():
    """动态读取 Steam 配置以获取所有 Steam 库所在路径"""
    libraries = []
    steam_path = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            val, _ = winreg.QueryValueEx(key, "SteamPath")
            if val and os.path.isdir(val):
                steam_path = os.path.abspath(val)
                libraries.append(steam_path)
    except Exception:
        pass

    if steam_path:
        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf_path):
            try:
                with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if '"path"' in line.lower():
                            parts = line.split('"')
                            if len(parts) >= 4:
                                p = parts[3].replace("\\\\", "\\")
                                if os.path.isdir(p) and p not in libraries:
                                    libraries.append(p)
            except Exception:
                pass
    return libraries

def get_system_logical_drives():
    """动态获取 Windows 当前所有已挂载的逻辑盘符"""
    drives = []
    try:
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
    except Exception:
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.exists(root):
                drives.append(root)
    return drives

def scan_disk_candidates():
    """动态扫描所有盘符与 Steam 库中的 Blender 安装位置"""
    candidates = []

    # 1. 动态扫描 Steam 库
    steam_libs = get_steam_libraries()
    for lib in steam_libs:
        cand = os.path.join(lib, "steamapps", "common", "Blender", "blender.exe")
        if os.path.isfile(cand):
            candidates.append(os.path.abspath(cand))

    # 2. 动态扫描所有系统盘
    drives = get_system_logical_drives()
    for drive in drives:
        patterns = [
            os.path.join(drive, "Program Files", "Blender Foundation", "Blender *", "blender.exe"),
            os.path.join(drive, "Program Files (x86)", "Blender Foundation", "Blender *", "blender.exe"),
            os.path.join(drive, "Program Files", "Blender *", "blender.exe"),
            os.path.join(drive, "SteamLibrary", "steamapps", "common", "Blender", "blender.exe"),
            os.path.join(drive, "Blender*", "blender.exe"),
        ]
        for pat in patterns:
            for m in glob.glob(pat):
                if os.path.isfile(m):
                    candidates.append(os.path.abspath(m))

    # 3. 动态检查用户 AppData 目录
    appdata_patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe"),
        os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender *\blender.exe"),
        os.path.expandvars(r"%ProgramFiles%\Blender Foundation\Blender *\blender.exe"),
        os.path.expandvars(r"%ProgramW6432%\Blender Foundation\Blender *\blender.exe"),
    ]
    for pat in appdata_patterns:
        for m in glob.glob(pat):
            if os.path.isfile(m):
                candidates.append(os.path.abspath(m))

    candidates = list(dict.fromkeys(candidates))
    candidates.sort(reverse=True)
    return candidates[0] if candidates else None

def find_blender():
    """全自动探测 Blender 路径"""
    b = get_env_blender()
    if b: return b

    b = get_path_blender()
    if b: return b

    b = get_registry_blender()
    if b: return b

    b = scan_disk_candidates()
    if b: return b

    return None

if __name__ == "__main__":
    path = find_blender()
    as_json = "--json" in sys.argv
    res = {
        "found": path is not None,
        "path": path,
        "message": f"Blender 路径已定位: {path}" if path else "未自动检测到 Blender，请通过环境变量 BLENDER_PATH 手动指定"
    }
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if path:
            print(path)
        else:
            print("NOT_FOUND", file=sys.stderr)
            sys.exit(1)
