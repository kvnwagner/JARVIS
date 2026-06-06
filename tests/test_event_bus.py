import unittest

from core.interfaces import Event
from infrastructure import events
from infrastructure.event_bus import InMemoryEventBus


class InMemoryEventBusTest(unittest.TestCase):
    def test_publish_notifies_named_and_wildcard_handlers(self):
        bus = InMemoryEventBus()
        received = []

        bus.subscribe(events.USER_MESSAGE, received.append)
        bus.subscribe(events.WILDCARD, received.append)

        event = Event(
            name=events.USER_MESSAGE,
            payload={"text": "hola"},
            source="test",
        )
        bus.publish(event)

        self.assertEqual(received, [event, event])

    def test_handler_error_does_not_stop_other_handlers(self):
        bus = InMemoryEventBus()
        received = []

        def failing_handler(_event):
            raise RuntimeError("boom")

        bus.subscribe(events.USER_MESSAGE, failing_handler)
        bus.subscribe(events.USER_MESSAGE, received.append)

        event = Event(
            name=events.USER_MESSAGE,
            payload={"text": "hola"},
            source="test",
        )
        bus.publish(event)

        self.assertEqual(received, [event])


if __name__ == "__main__":
    unittest.main()
