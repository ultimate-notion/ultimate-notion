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
tasklist.rename("My renamed tasklist")

same_tasklist = client.get_tasklist(tasklist.id)
task = tasklist.create_task("My new task")

assert same_tasklist == tasklist

tasklist.delete()
assert tasklist not in client.all_tasklists()

tasklist = client.create_tasklist("Personal tasklist")
task = tasklist.create_task("My first task")
assert task in tasklist.all_tasks()
same_task = tasklist.get_task(task.id)
assert same_task == task

same_task.delete()


from IPython import embed

embed()
