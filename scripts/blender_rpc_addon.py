"""
blender_rpc_addon.py
Vibe-Modeler 本地实时 RPC 服务插件 / 独立脚本
在 Blender 视口中运行此脚本即可开启本地 HTTP RPC 服务（端口 9876）。
Agent 可通过 HTTP API 实时向 Blender 视口推送建模指令、触发渲染和保存工程。
"""

bl_info = {
    "name": "Vibe-Modeler RPC Bridge",
    "author": "Antigravity",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Vibe-Modeler",
    "description": "提供与 Vibe-Modeler Agent 的本地实时交互 RPC 接口",
    "category": "3D View",
}

import os
import sys
import json
import queue
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import bpy
except ImportError:
    bpy = None

SERVER_PORT = 9876
_task_queue = queue.Queue()
_httpd = None
_server_thread = None

def _run_in_main_thread(func, args=(), kwargs=None):
    if kwargs is None: kwargs = {}
    res_box = {}
    event = threading.Event()

    def timer_callback():
        try:
            res_box["result"] = func(*args, **kwargs)
            res_box["success"] = True
        except Exception as e:
            res_box["error"] = str(e)
            res_box["success"] = False
        finally:
            event.set()
        return None # Unregister timer

    bpy.app.timers.register(timer_callback)
    event.wait(timeout=60.0)
    if not event.is_set():
        raise TimeoutError("Blender main thread execution timed out after 60s")
    if not res_box.get("success", False):
        raise RuntimeError(res_box.get("error", "Unknown error in main thread"))
    return res_box.get("result")

class VibeRPCHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress standard server log noise

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path == "/status":
            def get_status():
                return {
                    "alive": True,
                    "blender_version": list(bpy.app.version),
                    "active_scene": bpy.context.scene.name,
                    "object_count": len(bpy.context.scene.objects),
                    "selected_objects": [obj.name for obj in bpy.context.selected_objects]
                }
            try:
                res = _run_in_main_thread(get_status)
                self._send_json(200, res)
            except Exception as e:
                self._send_json(500, {"error": str(e)})
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {"code": body}

        if self.path == "/execute":
            code_str = payload.get("code", "")
            def exec_code():
                local_scope = {"bpy": bpy}
                exec(code_str, local_scope)
                return "Executed successfully"
            try:
                msg = _run_in_main_thread(exec_code)
                self._send_json(200, {"success": True, "message": msg})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == "/render":
            filepath = payload.get("filepath", os.path.abspath("rpc_render.png"))
            resolution_x = payload.get("width", 1280)
            resolution_y = payload.get("height", 720)
            engine = payload.get("engine", "BLENDER_EEVEE_NEXT")

            def do_render():
                scene = bpy.context.scene
                scene.render.image_settings.file_format = 'PNG'
                scene.render.filepath = filepath
                scene.render.resolution_x = resolution_x
                scene.render.resolution_y = resolution_y
                if hasattr(scene.render, "engine"):
                    try:
                        scene.render.engine = engine
                    except Exception:
                        pass
                bpy.ops.render.render(write_still=True)
                return os.path.abspath(filepath)

            try:
                saved_path = _run_in_main_thread(do_render)
                self._send_json(200, {"success": True, "filepath": saved_path})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif self.path == "/save":
            filepath = payload.get("filepath", os.path.abspath("scene.blend"))
            def do_save():
                bpy.ops.wm.save_as_mainfile(filepath=filepath)
                return os.path.abspath(filepath)
            try:
                saved_blend = _run_in_main_thread(do_save)
                self._send_json(200, {"success": True, "filepath": saved_blend})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

def start_server():
    global _httpd, _server_thread
    if _httpd is not None:
        return
    _httpd = HTTPServer(("127.0.0.1", SERVER_PORT), VibeRPCHandler)
    _server_thread = threading.Thread(target=_httpd.serve_forever, daemon=True)
    _server_thread.start()
    print(f"[*] Vibe-Modeler RPC Server running on http://127.0.0.1:{SERVER_PORT}")

def stop_server():
    global _httpd, _server_thread
    if _httpd:
        _httpd.shutdown()
        _httpd.server_close()
        _httpd = None
        _server_thread = None
        print("[*] Vibe-Modeler RPC Server stopped")

def register():
    start_server()

def unregister():
    stop_server()

if __name__ == "__main__":
    if bpy:
        start_server()
    else:
        print("Please run this script inside Blender or via 'blender -P blender_rpc_addon.py'")
