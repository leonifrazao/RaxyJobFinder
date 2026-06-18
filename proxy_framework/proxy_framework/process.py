from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

from .interfaces import ProxyProcessManager
from .logging_utils import log
from .models import Outbound
from .parser import decode_bytes


class ProcessManager(ProxyProcessManager):
    def __init__(self) -> None:
        self._port_allocation_lock = threading.Lock()
        self._allocated_ports: set[int] = set()

    @staticmethod
    def shutil_which(cmd: str) -> Optional[str]:
        if hasattr(shutil, "which") and callable(shutil.which):
            return shutil.which(cmd)

        paths = os.environ.get("PATH", "").split(os.pathsep)
        exts = [""]
        if os.name == "nt":
            exts = os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").lower().split(";")
        for directory in paths:
            candidate = Path(directory) / cmd
            if candidate.exists() and candidate.is_file() and os.access(str(candidate), os.X_OK):
                return str(candidate)
            if os.name == "nt":
                base = Path(directory) / cmd
                for ext in exts:
                    alt = base.with_suffix(ext)
                    if alt.exists() and alt.is_file() and os.access(str(alt), os.X_OK):
                        return str(alt)
        return None

    @classmethod
    def which_xray(cls) -> str:
        env_path = os.environ.get("XRAY_PATH")
        if env_path and Path(env_path).exists():
            return env_path
        for candidate in ("xray", "xray.exe", "v2ray", "v2ray.exe"):
            found = cls.shutil_which(candidate)
            if found:
                return found
        message = "Nao foi possivel localizar xray/v2ray. Instale xray-core ou configure XRAY_PATH."
        log.critical(message)
        raise RuntimeError(message)

    def find_available_port(self) -> int:
        with self._port_allocation_lock:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
                if port in self._allocated_ports:
                    return self.find_available_port()
                self._allocated_ports.add(port)
                return port
            except OSError as exc:
                raise RuntimeError("Nao foi possivel alocar uma porta TCP disponivel.") from exc
            finally:
                sock.close()

    def release_port(self, port: Optional[int]) -> None:
        if port is None:
            return
        with self._port_allocation_lock:
            self._allocated_ports.discard(port)

    @staticmethod
    def terminate_process(proc: Optional[subprocess.Popen], *, wait_timeout: float = 3.0) -> None:
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=wait_timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    @staticmethod
    def safe_remove_dir(path: Optional[Path]) -> None:
        if path is None:
            return
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass

    def make_xray_config_http_inbound(self, port: int, outbound: Outbound) -> Dict[str, Any]:
        cfg = {
            "log": {"loglevel": "warning"},
            "inbounds": [{
                "tag": "http-in",
                "listen": "127.0.0.1",
                "port": port,
                "protocol": "http",
                "settings": {},
            }],
            "outbounds": [
                outbound.config,
                {"tag": "direct", "protocol": "freedom", "settings": {}},
                {"tag": "block", "protocol": "blackhole", "settings": {}},
            ],
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [{
                    "type": "field",
                    "outboundTag": outbound.config.get("tag", outbound.tag),
                    "network": "tcp,udp",
                }],
            },
        }
        if "tag" not in cfg["outbounds"][0]:
            cfg["outbounds"][0]["tag"] = outbound.tag
        return cfg

    def launch_bridge_with_diagnostics(self, xray_bin: str, cfg: Dict[str, Any], name: str) -> Tuple[subprocess.Popen, Path]:
        tmpdir = Path(tempfile.mkdtemp(prefix=f"xray_{name}_"))
        cfg_path = tmpdir / "config.json"
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

        proc = subprocess.Popen(
            [xray_bin, "-config", str(cfg_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc, cfg_path

    @contextmanager
    def temporary_bridge(
        self,
        outbound: Outbound,
        *,
        tag_prefix: str = "temp",
    ) -> Generator[Tuple[int, subprocess.Popen], None, None]:
        port: Optional[int] = None
        proc: Optional[subprocess.Popen] = None
        cfg_dir: Optional[Path] = None

        try:
            port = self.find_available_port()
            cfg = self.make_xray_config_http_inbound(port, outbound)
            xray_bin = self.which_xray()
            proc, cfg_path = self.launch_bridge_with_diagnostics(xray_bin, cfg, f"{tag_prefix}_{outbound.tag}")
            cfg_dir = cfg_path.parent

            time.sleep(1.0)
            if proc.poll() is not None:
                error_output = ""
                if proc.stderr:
                    error_output = decode_bytes(proc.stderr.read()).strip()
                raise RuntimeError(
                    "Processo Xray temporario finalizou antes do teste. "
                    f"Erro: {error_output or 'Nenhuma saida de erro.'}"
                )

            yield port, proc
        finally:
            self.terminate_process(proc, wait_timeout=2)
            self.safe_remove_dir(cfg_dir)
            if port is not None:
                self.release_port(port)
