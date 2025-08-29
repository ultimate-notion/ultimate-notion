"""All definitions and enumerations"""

from __future__ import annotations

from enum import Enum

# ToDo: Let Enums inherit form StrEnum instead of Enum & str, when we require Python >= 3.11


class SortDirection(str, Enum):
    """Sort direction options."""

    ASCENDING = 'ascending'
    DESCENDING = 'descending'


class TimestampKind(str, Enum):
    """Possible timestamp types."""

    CREATED_TIME = 'created_time'
    LAST_EDITED_TIME = 'last_edited_time'


class VState(str, Enum):
    """Verification states for pages in wiki databases."""

    VERIFIED = 'verified'
    UNVERIFIED = 'unverified'


class Color(str, Enum):
    """Basic colors

    DEFAULT is a light gray, which is the default color in the Notion App.
    """

    DEFAULT = 'default'
    GRAY = 'gray'
    BROWN = 'brown'
    ORANGE = 'orange'
    YELLOW = 'yellow'
    GREEN = 'green'
    BLUE = 'blue'
    PURPLE = 'purple'
    PINK = 'pink'
    RED = 'red'


class FormulaType(str, Enum):
    """Formula types for formulas.

    The type of the formula as well as the mapping to the Notion API keyword when filtering in a query.
    """

    NUMBER = 'number', 'number'
    STRING = 'string', 'string'
    BOOLEAN = 'boolean', 'checkbox'  # inconsistency in the Notion API
    DATE = 'date', 'date'

    formula_kwarg: str

    def __new__(cls, value: str, formula_kwarg: str = '') -> FormulaType:
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.formula_kwarg = formula_kwarg
        return obj


class RollupType(str, Enum):
    """Rollup types for rollups."""

    NUMBER = 'number'
    DATE = 'date'
    ARRAY = 'array'
    INCOMPLETE = 'incomplete'
    UNSUPPORTED = 'unsupported'


class ArrayQuantifier(str, Enum):
    """Array quantifiers for rollups."""

    ANY = 'any'
    EVERY = 'every'
    NONE = 'none'


class OptionGroupType(str, Enum):
    """Option group type of the Status property."""

    TO_DO = 'to_do'
    IN_PROGRESS = 'in_progress'
    COMPLETE = 'complete'


class BGColor(str, Enum):
    """Background colors for most textual blocks, e.g. paragraphs, callouts, etc."""

    DEFAULT = 'default'
    GRAY = 'gray_background'
    BROWN = 'brown_background'
    ORANGE = 'orange_background'
    YELLOW = 'yellow_background'
    GREEN = 'green_background'
    BLUE = 'blue_background'
    PURPLE = 'purple_background'
    PINK = 'pink_background'
    RED = 'red_background'


class FileUploadStatus(str, Enum):
    """Status of a file upload."""

    PENDING = 'pending'
    UPLOADED = 'uploaded'
    EXPIRED = 'expired'
    FAILED = 'failed'


class FileUploadMode(str, Enum):
    """File upload modes."""

    SINGLE_PART = 'single_part'
    MULTI_PART = 'multi_part'
    EXTERNAL_URL = 'external_url'


class CodeLang(str, Enum):
    """Coding languages for code blocks."""

    ABAP = 'abap'
    ARDUINO = 'arduino'
    BASH = 'bash'
    BASIC = 'basic'
    C = 'c'
    CLOJURE = 'clojure'
    COFFEESCRIPT = 'coffeescript'
    CPP = 'c++'
    CSHARP = 'c#'
    CSS = 'css'
    DART = 'dart'
    DIFF = 'diff'
    DOCKER = 'docker'
    ELIXIR = 'elixir'
    ELM = 'elm'
    ERLANG = 'erlang'
    FLOW = 'flow'
    FORTRAN = 'fortran'
    FSHARP = 'f#'
    GHERKIN = 'gherkin'
    GLSL = 'glsl'
    GO = 'go'
    GRAPHQL = 'graphql'
    GROOVY = 'groovy'
    HASKELL = 'haskell'
    HTML = 'html'
    JAVA = 'java'
    JAVASCRIPT = 'javascript'
    JSON = 'json'
    JULIA = 'julia'
    KOTLIN = 'kotlin'
    LATEX = 'latex'
    LESS = 'less'
    LISP = 'lisp'
    LIVESCRIPT = 'livescript'
    LUA = 'lua'
    MAKEFILE = 'makefile'
    MARKDOWN = 'markdown'
    MARKUP = 'markup'
    MATLAB = 'matlab'
    MERMAID = 'mermaid'
    NIX = 'nix'
    OBJECTIVE_C = 'objective-c'
    OCAML = 'ocaml'
    PASCAL = 'pascal'
    PERL = 'perl'
    PHP = 'php'
    PLAIN_TEXT = 'plain text'
    POWERSHELL = 'powershell'
    PROLOG = 'prolog'
    PROTOBUF = 'protobuf'
    PYTHON = 'python'
    R = 'r'
    REASON = 'reason'
    RUBY = 'ruby'
    RUST = 'rust'
    SASS = 'sass'
    SCALA = 'scala'
    SCHEME = 'scheme'
    SCSS = 'scss'
    SHELL = 'shell'
    SQL = 'sql'
    SWIFT = 'swift'
    TOML = 'toml'
    TYPESCRIPT = 'typescript'
    VB_NET = 'vb.net'
    VERILOG = 'verilog'
    VHDL = 'vhdl'
    VISUAL_BASIC = 'visual basic'
    WEBASSEMBLY = 'webassembly'
    XML = 'xml'
    YAML = 'yaml'
    MISC = 'java/c/c++/c#'


class AggFunc(str, Enum):
    """Aggregation functions for formulas.

    The categories naming corresonds mostly to the naming in the Notion App but
    also eliminates some inconsistencies. The first part of the tuple is the
    string used in the Notion API, the second part is an alias corresoinding to
    the defined category num.
    """

    SHOW_ORIGINAL = 'show_original', 'show_original'
    SHOW_UNIQUE = 'show_unique', 'show_unique'

    # Count
    COUNT_ALL = 'count', 'count_all'
    COUNT_VALUES = 'count_values', 'count_values'
    COUNT_UNIQUE_VALUES = 'unique', 'count_unique_values'
    COUNT_EMPTY = 'empty', 'count_empty'
    COUNT_NOT_EMPTY = 'not_empty', 'count_not_empty'
    COUNT_CHECKED = 'checked', 'count_checked'  # just called 'checked' in the Notion App
    COUNT_UNCHECKED = 'unchecked', 'count_unchecked'  # just called 'unchecked' in the Notion App
    COUNT_PER_GROUP = 'count_per_group', 'count_per_group'  # only for type 'status'

    # Percent
    PERCENT_EMPTY = 'percent_empty', 'percent_empty'
    PERCENT_NOT_EMPTY = 'percent_not_empty', 'percent_not_empty'
    PERCENT_CHECKED = 'percent_checked', 'percent_checked'
    PERCENT_PER_GROUP = 'percent_per_group', 'percent_per_group'  # only for type 'status'

    # Date
    DATE_RANGE = 'date_range', 'date_range'
    EARLIEST_DATE = 'earliest_date', 'earliest_date'
    LATEST_DATE = 'latest_date', 'latest_date'

    # More options, e.g. for numbers
    SUM = 'sum', 'sum'
    AVERAGE = 'average', 'average'
    MEDIAN = 'median', 'median'
    MIN = 'min', 'min'
    MAX = 'max', 'max'
    RANGE = 'range', 'range'

    alias: str

    def __new__(cls, value: str, alias: str = '') -> AggFunc:
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.alias = alias
        return obj

    @classmethod
    def from_alias(cls, alias: str) -> AggFunc:
        for item in cls:
            if item.alias == alias:
                return item
        msg = f'{alias} is not a valid {cls.__name__}'
        raise ValueError(msg)


class NumberFormat(str, Enum):
    """Number formats for numbers."""

    NUMBER = 'number'
    NUMBER_WITH_COMMAS = 'number_with_commas'
    PERCENT = 'percent'
    DOLLAR = 'dollar'
    CANADIAN_DOLLAR = 'canadian_dollar'
    AUSTRALIAN_DOLLAR = 'australian_dollar'
    EURO = 'euro'
    POUND = 'pound'
    YEN = 'yen'
    RUBLE = 'ruble'
    RUPEE = 'rupee'
    WON = 'won'
    YUAN = 'yuan'
    REAL = 'real'
    LIRA = 'lira'
    RUPIAH = 'rupiah'
    FRANC = 'franc'
    HONG_KONG_DOLLAR = 'hong_kong_dollar'
    NEW_ZEALAND_DOLLAR = 'new_zealand_dollar'
    KRONA = 'krona'
    NORWEGIAN_KRONE = 'norwegian_krone'
    MEXICAN_PESO = 'mexican_peso'
    RAND = 'rand'
    NEW_TAIWAN_DOLLAR = 'new_taiwan_dollar'
    DANISH_KRONE = 'danish_krone'
    ZLOTY = 'zloty'
    BAHT = 'baht'
    FORINT = 'forint'
    KORUNA = 'koruna'
    SHEKEL = 'shekel'
    CHILEAN_PESO = 'chilean_peso'
    PHILIPPINE_PESO = 'philippine_peso'
    DIRHAM = 'dirham'
    COLOMBIAN_PESO = 'colombian_peso'
    RIYAL = 'riyal'
    RINGGIT = 'ringgit'
    LEU = 'leu'
    ARGENTINE_PESO = 'argentine_peso'
    URUGUAYAN_PESO = 'uruguayan_peso'
