import unittest

from core.interfaces import Event, Tool, ToolResult
from infrastructure import events
from infrastructure.event_bus import InMemoryEventBus
from tools import ToolRegistry


class EchoTool(Tool):
    name = "echo"
    description = "Devuelve el texto recibido."
    parameters_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=True, output=params["text"])


class ExplodingTool(Tool):
    name = "explode"
    description = "Falla para probar el contrato."
    parameters_schema = {"type": "object", "properties": {}}

    def execute(self, params: dict) -> ToolResult:
        raise RuntimeError("fallo controlado")


class ToolRegistryTest(unittest.TestCase):
    def test_executes_tool_from_llm_tool_call_event(self):
        bus = InMemoryEventBus()
        registry = ToolRegistry(bus)
        registry.register(EchoTool())
        received = []

        bus.subscribe(events.WILDCARD, received.append)

        bus.publish(
            Event(
                name=events.LLM_TOOL_CALL,
                payload={"tool": "echo", "params": {"text": "listo"}},
                source="llm",
            )
        )

        event_names = [event.name for event in received]
        self.assertIn(events.TOOL_STARTED, event_names)
        self.assertIn(events.TOOL_EXECUTED, event_names)

        executed = [event for event in received if event.name == events.TOOL_EXECUTED][0]
        self.assertEqual(executed.source, "echo")
        self.assertEqual(executed.payload["output"], "listo")
        self.assertEqual(executed.payload["requested_by"], "llm")

    def test_accepts_args_alias_from_llm_tool_call_event(self):
        bus = InMemoryEventBus()
        registry = ToolRegistry(bus)
        registry.register(EchoTool())
        executed_events = []
        bus.subscribe(events.TOOL_EXECUTED, executed_events.append)

        bus.publish(
            Event(
                name=events.LLM_TOOL_CALL,
                payload={"tool": "echo", "args": {"text": "alias"}},
                source="llm",
            )
        )

        self.assertEqual(executed_events[0].payload["output"], "alias")

    def test_unknown_tool_publishes_failure(self):
        bus = InMemoryEventBus()
        ToolRegistry(bus)
        failures = []
        bus.subscribe(events.TOOL_FAILED, failures.append)

        bus.publish(
            Event(
                name=events.LLM_TOOL_CALL,
                payload={"tool": "missing", "params": {}},
                source="llm",
            )
        )

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].source, "missing")
        self.assertFalse(failures[0].payload["success"])

    def test_tool_exception_is_converted_to_failure_result(self):
        bus = InMemoryEventBus()
        registry = ToolRegistry(bus)
        registry.register(ExplodingTool())
        failures = []
        bus.subscribe(events.TOOL_FAILED, failures.append)

        result = registry.execute("explode", {})

        self.assertFalse(result.success)
        self.assertEqual(failures[0].payload["error"], "fallo controlado")


if __name__ == "__main__":
    unittest.main()
