"""Example showing how to sync your tasks between Google Tasks and Notion.

Note: Follow this quickstart guide first to enable the Google API and create the necessary credentials:
https://developers.google.com/tasks/quickstart/python
"""

from ultimate_notion.adapters.google import GTasksClient

client = GTasksClient(read_only=False)
