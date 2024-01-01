"""Example showing how to sync your tasks between Google Tasks and Notion.

Note: Follow this quickstart guide first to enable the Google API and create the necessary credentials:
https://developers.google.com/tasks/quickstart/python

Create a `.ultimate-notion/config.toml` file in your home directory with the following content:
```toml
[Google]
client_secret_json = 'client_secret.json'
token_json = 'token.json'
```

Put the `client_secret.json` file from the Google API in the same directory as the `config.toml` file.
The `token.json` file will be created automatically after the first run.
"""

from ultimate_notion.adapters.google import GTasksClient

client = GTasksClient(read_only=False)

all_tasklists = client.all_tasklists()
tasklist = client.create_tasklist("My new tasklist")
assert tasklist.title == "My new tasklist"
tasklist.title = "My renamed tasklist"
assert tasklist.title == "My renamed tasklist"

same_tasklist = client.get_tasklist(tasklist.id)
task = tasklist.create_task("My new task")

assert same_tasklist == tasklist

tasklist.delete()
assert tasklist not in client.all_tasklists()

tasklist = client.create_tasklist("Personal tasklist")
task = tasklist.create_task("My first task")
assert task.title == "My first task"
task.title = "My renamed task"
assert task.title == "My renamed task"
assert task in tasklist.all_tasks()
same_task = tasklist.get_task(task.id)
assert same_task == task

same_task.delete()
assert same_task.deleted is True

task = tasklist.create_task("Task with notes")
task.notes = "My notes"
assert task.notes == "My notes"
assert not task.completed
task.completed = True
assert task.completed


task2 = tasklist.create_task("Another task")
task.completed = False

task2.move(parent=task)
