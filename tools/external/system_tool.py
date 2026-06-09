"""
Tool: system
Consulta el estado del sistema: CPU, RAM, disco, IP local y procesos.
Usa psutil — sin internet, sin API key.
"""
import socket
import psutil
from core.interfaces import Tool, ToolResult


class SystemTool(Tool):
    name = "system"
    description = (
        "Consulta el estado del sistema local: uso de CPU, RAM disponible, "
        "espacio en disco, IP local y procesos que más recursos consumen. "
        "Usa esto cuando el usuario pregunte por el rendimiento del computador, "
        "cuánta memoria tiene libre, qué tan cargado está el procesador, "
        "cuánto espacio queda en el disco o cuál es su IP."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "enum": ["all", "cpu", "ram", "disk", "ip", "processes"],
                "description": (
                    "'all' = resumen completo del sistema (por defecto), "
                    "'cpu' = uso del procesador, "
                    "'ram' = memoria RAM, "
                    "'disk' = espacio en disco, "
                    "'ip' = dirección IP local, "
                    "'processes' = top 5 procesos por CPU"
                )
            }
        },
        "required": []
    }

    def execute(self, params: dict) -> ToolResult:
        query = params.get("query", "all").strip().lower()

        try:
            if query == "cpu":
                return ToolResult.ok(self._cpu())
            if query == "ram":
                return ToolResult.ok(self._ram())
            if query == "disk":
                return ToolResult.ok(self._disk())
            if query == "ip":
                return ToolResult.ok(self._ip())
            if query == "processes":
                return ToolResult.ok(self._processes())
            # "all" o cualquier otro valor
            return ToolResult.ok(self._all())
        except Exception as e:
            return ToolResult.fail(f"Error al consultar el sistema: {e}")

    # ── Secciones individuales ────────────────────────────────────

    def _cpu(self) -> str:
        percent = psutil.cpu_percent(interval=1)
        freq = psutil.cpu_freq()
        cores = psutil.cpu_count(logical=False)
        threads = psutil.cpu_count(logical=True)
        freq_str = f"{freq.current:.0f} MHz" if freq else "N/A"
        return (
            f"🖥️  CPU\n"
            f"   Uso actual:  {percent}%\n"
            f"   Núcleos:     {cores} físicos / {threads} lógicos\n"
            f"   Frecuencia:  {freq_str}"
        )

    def _ram(self) -> str:
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024 ** 3)
        used_gb = mem.used / (1024 ** 3)
        free_gb = mem.available / (1024 ** 3)
        return (
            f"🧠  RAM\n"
            f"   Total:       {total_gb:.1f} GB\n"
            f"   En uso:      {used_gb:.1f} GB ({mem.percent}%)\n"
            f"   Disponible:  {free_gb:.1f} GB"
        )

    def _disk(self) -> str:
        disk = psutil.disk_usage("C:\\")
        total_gb = disk.total / (1024 ** 3)
        used_gb = disk.used / (1024 ** 3)
        free_gb = disk.free / (1024 ** 3)
        return (
            f"💾  Disco (C:)\n"
            f"   Total:       {total_gb:.1f} GB\n"
            f"   Usado:       {used_gb:.1f} GB ({disk.percent}%)\n"
            f"   Libre:       {free_gb:.1f} GB"
        )

    def _ip(self) -> str:
        try:
            # Truco: conectar a un host externo sin enviar datos para obtener la IP saliente
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
        except Exception:
            local_ip = socket.gethostbyname(socket.gethostname())
        hostname = socket.gethostname()
        return (
            f"🌐  Red\n"
            f"   IP local:    {local_ip}\n"
            f"   Hostname:    {hostname}"
        )

    def _processes(self) -> str:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Ordenar por CPU, tomar top 5
        top = sorted(procs, key=lambda x: x["cpu_percent"] or 0, reverse=True)[:5]
        lines = ["⚡  Top 5 procesos por CPU"]
        for p in top:
            cpu = p["cpu_percent"] or 0
            mem = p["memory_percent"] or 0
            lines.append(f"   {p['name']:<28} CPU: {cpu:5.1f}%  RAM: {mem:.1f}%")
        return "\n".join(lines)

    def _all(self) -> str:
        return "\n\n".join([
            self._cpu(),
            self._ram(),
            self._disk(),
            self._ip(),
            self._processes(),
        ])