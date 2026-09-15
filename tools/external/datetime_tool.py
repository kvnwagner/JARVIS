"""
Tool: datetime
Consulta la hora, fecha, día de la semana o una combinación de todo.
No requiere API key — usa el reloj del sistema donde corre Jarvis.
"""
from datetime import datetime
from core.interfaces import Tool, ToolResult

DIAS = [
    "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo",
]

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class DateTimeTool(Tool):
    name = "datetime"
    description = (
        "Consulta la hora actual, la fecha actual, el día de la semana, "
        "o toda la información junta. Usa esto cuando el usuario pregunte "
        "'qué hora es', 'qué día es hoy', 'en qué fecha estamos', etc."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "enum": ["time", "date", "weekday", "all"],
                "description": (
                    "'time' = solo la hora, "
                    "'date' = solo la fecha, "
                    "'weekday' = solo el día de la semana, "
                    "'all' = hora, fecha y día completos (por defecto)"
                ),
            }
        },
        "required": [],
    }

    def execute(self, params: dict) -> ToolResult:
        query = params.get("query", "all").strip().lower()
        now = datetime.now()

        try:
            if query == "time":
                return ToolResult.ok(f"Son las {now.strftime('%H:%M')}.")
            if query == "date":
                return ToolResult.ok(
                    f"Hoy es {now.day} de {MESES[now.month - 1]} de {now.year}."
                )
            if query == "weekday":
                return ToolResult.ok(f"Hoy es {DIAS[now.weekday()]}.")

            # "all" o cualquier otro valor
            return ToolResult.ok(
                f"Hoy es {DIAS[now.weekday()]}, {now.day} de {MESES[now.month - 1]} "
                f"de {now.year}, y son las {now.strftime('%H:%M')}."
            )
        except Exception as e:
            return ToolResult.fail(f"Error al consultar la hora: {e}")