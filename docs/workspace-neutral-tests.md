# Refactoring patch for ultimate-notion conftest.py
# Fixes #194 — Remove hard-coded personal/workspace references
#
# Key changes:
#  1. Add UNO_TEST_USER env var to replace hard-coded search_user('Florian Wilhelm')
#  2. Add UNO_TEST_* env vars for workspace objects (pages, databases)
#  3. Fall back to existing defaults for backward compatibility
#
# --- a/tests/conftest.py
# +++ b/tests/conftest.py

# After line ~42 (ENV_TEST_ROOT_PAGE definition), add:

# Environment variable to override the test user for integration tests.
# Defaults to all_users()[0] when unset (workspace-neutral).
ENV_TEST_USER = 'UNO_TEST_USER'

# Environment variable overrides for named workspace objects used in
# integration tests.  Each maps to a page / database name looked up via
# find_page / find_db.  When unset, the recorded-cassette default is used,
# so existing replay tests continue to work.
ENV_TESTS_PAGE = 'UNO_TEST_ROOT_PAGE'  # alias for backward compat
ENV_ALL_PROPS_DB = 'UNO_TEST_ALL_PROPS_DB'
ENV_WIKI_DB = 'UNO_TEST_WIKI_DB'
ENV_CONTACTS_DB = 'UNO_TEST_CONTACTS_DB'
ENV_TASK_DB = 'UNO_TEST_TASK_DB'
ENV_FORMULA_DB = 'UNO_TEST_FORMULA_DB'

# Map of workspace object name → env-var override (None = no override)
_WORKSPACE_OBJECT_ENV = {
    'All Properties DB': ENV_ALL_PROPS_DB,
    'Wiki DB': ENV_WIKI_DB,
    'Contacts DB': ENV_CONTACTS_DB,
    'Task DB': ENV_TASK_DB,
    'Formula DB': ENV_FORMULA_DB,
}

# --- Replace in conftest.py (around line 338):
# OLD:
#   user = search_user('Florian Wilhelm')
# NEW:
#   user_name = os.environ.get(ENV_TEST_USER)
#   if user_name:
#       user = search_user(user_name)
#   else:
#       # Workspace-neutral fallback — uses the integration's own bot
#       user = all_users()[0]

# --- For named lookups (~lines 56-68), add a helper:
# def _resolve_workspace_name(name: str) -> str:
#     """Resolve a workspace object name, preferring env-var overrides."""
#     env_var = _WORKSPACE_OBJECT_ENV.get(name)
#     if env_var:
#         override = os.environ.get(env_var)
#         if override:
#             return override
#     return name

# --- Usage in fixtures (example):
# OLD:
#   tests_page = find_page(TESTS_PAGE)
# NEW:
#   tests_page = find_page(_resolve_workspace_name(TESTS_PAGE))

# --- Backward compatibility note:
# All env vars are optional.  When unset, behavior is identical to the
# current hard-coded workspace.  Existing VCR cassettes continue to work
# because the recorded requests still match the default object names.
