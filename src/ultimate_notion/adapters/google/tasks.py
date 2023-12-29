from enum import Enum
from typing import TYPE_CHECKING

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

if TYPE_CHECKING:
    from ultimate_notion.adapters.config import Config


class Scope(Enum, str):
    # Allows read-only access to Google Tasks
    TASKS_RO = 'https://www.googleapis.com/auth/tasks.readonly'
    # Allows read/write access to Google Tasks
    TASKS_RW = 'https://www.googleapis.com/auth/tasks'


def gtask_client(scopes: list[Scope], config: Config) -> gspread.client.Client:
    """Creates the GSheet client using our configuration

    Read [GSpread](https://docs.gspread.org/) for usage details
    """
    if (secret_path := config.Google.client_secret_json) is None:
        msg = 'You have to set Google.client_secret_json in your config.toml!'
        raise RuntimeError(msg)
    if (token_path := config.Google.token_json) is None:
        msg = 'You have to set Google.token_json in your config.toml!'
        raise RuntimeError(msg)

    gc = gspread.oauth(
        scopes=[scope.value for scope in scopes],
        credentials_filename=str(secret_path),
        authorized_user_filename=str(token_path),
    )
    return gc


class PermissionDeniedError(Exception):
    """Error for APIError with status PERMISSION_DENIED

    Most likely thrown in cases when the scope is not `GSHEET_RW` or the token needs to be updated accordingly.
    """


class GSheetClient:
    """Google API to easily handle GSheets and other files on GDrive

    By default, only the least permissive scope `GSHEET_RO` in case of `read_only = True` is used.
    """

    def __init__(self, config: Config | None = None, *, read_only: bool = True):
        self._read_only = read_only
        if read_only:
            self._scopes = [Scope.GSHEET_RO]
        else:
            self._scopes = [Scope.GSHEET_RW]
        if config is None:
            config = get_cfg()
        self._config = config
        self.gc = gspread_client(self._scopes, config)  # gspread client for more functionality

    def recreate_token(self):
        """Recreate the current token using the scopes given at initialization"""
        self._config.Google.token_json.unlink(missing_ok=True)
        self.gc = gspread_client(self._scopes, self._config)

    def _wait_for_worksheet(self, spreadsheet_id: str, worksheet_name: str):
        """Wait for the worksheet to come into existence"""
        spreadsheet = self.gc.open_by_key(spreadsheet_id)
        while worksheet_name not in [ws.title for ws in spreadsheet.worksheets()]:
            time.sleep(1)

    def gsheet(
        self, spreadsheet_id: str, worksheet_name: str | None = None, *, create_ws: bool = False
    ) -> Worksheet | Spreadsheet:
        """Retrieve a Google sheet by its id and the name

        Open a Google sheet in your browser and check the URL to retrieve the id, e.g.:
        https://docs.google.com/spreadsheets/d/SPREEDSHEET_ID/edit...

        If the spreadsheet as several worksheets (check the lower bar) then `worksheet_name` can be used to
        specify a specific one.
        """
        spreadsheet = self.gc.open_by_key(spreadsheet_id)
        if worksheet_name is None:
            return spreadsheet
        elif worksheet_name in [ws.title for ws in spreadsheet.worksheets()]:
            return spreadsheet.worksheet(worksheet_name)
        elif create_ws:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=100, cols=20)
            self._wait_for_worksheet(spreadsheet_id, worksheet_name)
            return worksheet
        else:
            return spreadsheet.worksheet(worksheet_name)  # raises exception

    def _exception_feedback(self, error: APIError):
        if error.response.json()['error']['status'] == 'PERMISSION_DENIED':
            if self._read_only:
                msg = 'For saving `read_only=False` is needed when initializing this client!'
                raise PermissionDeniedError(msg) from error
            else:
                msg = 'Attempt to recreate your current token by calling the method `recreate_token()` first!'
                raise PermissionDeniedError(msg) from error
        else:
            raise error

    def save_df_as_gsheet(
        self,
        df: pd.DataFrame,
        spreadsheet_id: str,
        worksheet_name: str,
        *,
        create_ws: bool = False,
        default_fmt: bool = True,
        **kwargs: str | (bool | int),
    ):
        """Save the given dataframe as worksheet in a spreadsheet

        Make sure that the scope passed gives you write permissions

        Args:
            df: dataframe to save
            spreadsheet_id: id of the Google spreadsheet
            worksheet_name: name of the worksheet within the spreadsheet
            create_ws: create the worksheet if non-existent
            default_fmt: apply default formatter `BasicFormatter`
            **kwargs: extra keyword arguments passed to `set_with_dataframe`
        """
        worksheet = self.gsheet(spreadsheet_id, worksheet_name, create_ws=create_ws)
        # make sure it's really only the dataframe, not some residue
        self.clear_gsheet(spreadsheet_id, worksheet_name)
        params = {'resize': True} | dict(**kwargs)  # set sane defaults
        try:
            set_with_dataframe(worksheet, df, **params)
            if default_fmt:
                format_with_dataframe(worksheet, df)
        except APIError as error:
            self._exception_feedback(error)

    def clear_gsheet(self, spreadsheet_id: str, worksheet_name: str):
        """Clear the worksheet including values, formatting, filtering, etc."""
        worksheet = self.gsheet(spreadsheet_id, worksheet_name, create_ws=False)
        default_fmt = get_default_format(worksheet.spreadsheet)
        wrange = worksheet_range(worksheet)
        try:
            worksheet.clear()
            worksheet.clear_basic_filter()
            format_cell_range(worksheet, wrange, default_fmt)
            rules = get_conditional_format_rules(worksheet)
            rules.clear()
            rules.save()
            set_data_validation_for_cell_range(worksheet, wrange, None)
        except APIError as error:
            self._exception_feedback(error)

    def gsheet_as_df(self, spreadsheet_id: str, worksheet_name: str, **kwargs: str | (bool | int)) -> pd.DataFrame:
        """Returns a worksheet as dataframe"""
        worksheet = self.gsheet(spreadsheet_id, worksheet_name)
        df = get_as_dataframe(worksheet, **kwargs)
        # remove Nan rows & columns as they are exported by default
        df.dropna(how='all', inplace=True, axis=0)
        df.dropna(how='all', inplace=True, axis=1)
        return df


def gsheet_col(idx: int) -> str:
    """Convert a column index to Google Sheet range notation, e.g. A, BE, etc."""
    idx += 1
    chars = []
    while idx:
        chars.append(string.ascii_uppercase[(idx % 26) - 1])
        idx //= 27
    return ''.join(chars[::-1])


def gsheet_rows_for_fmt(mask: pd.Series, n_cols: int) -> list[str]:
    """Get the Google Sheet row range specifications for formatting"""
    rows = pd.Series(np.argwhere(mask.to_numpy()).reshape(-1) + 2)  # +2 since 1-index and header
    last_col = gsheet_col(n_cols - 1)  # last index
    rows = rows.map(lambda x: f'A{x}:{last_col}{x}')
    return rows.to_list()


def worksheet_range(worksheet: Worksheet) -> str:
    """Returns a range encompassing the whole worksheet"""
    last_row = worksheet.row_count
    last_col = gsheet_col(worksheet.col_count)
    return f'A1:{last_col}{last_row}'


def mark_rows(worksheet, mask: pd.Series, color: ColorType):
    """Mark rows specified by a mask (condition) with a given color

    Color can be a tuple of RGB values or a Matplotlib string specification:
    https://matplotlib.org/stable/gallery/color/named_colors.html#css-colors
    """
    rows = gsheet_rows_for_fmt(mask, worksheet.col_count)
    fmt = cellFormat(backgroundColor=Color(*to_rgb(color)))
    if rows:
        format_cell_ranges(worksheet, [(rng, fmt) for rng in rows])


def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no valid credentials, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Google Tasks API
    service = build('tasks', 'v1', credentials=creds)

    # Example: List tasklists
    results = service.tasklists().list(maxResults=10).execute()
    items = results.get('items', [])

    if not items:
        print('No task lists found.')
    else:
        print('Task lists:')
        for item in items:
            print(f"{item['title']} ({item['id']})")
