"""Google adapters."""
# ToDo: Extract some more functionality from the Google Task adapter into this level
# like GObject and the client code if it is the same over all Google adapters.

from ultimate_notion.adapters.google.tasks import GTasksClient, SyncGTasks

__all__ = ['GTasksClient', 'SyncGTasks']
