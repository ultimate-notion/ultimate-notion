"""All definitions and enumerations"""

from __future__ import annotations

from enum import Enum


class VState(str, Enum):
    """Verification states for pages in wiki databases."""

    VERIFIED = 'verified'
    UNVERIFIED = 'unverified'


class Color(str, Enum):
    """Basic colors"""

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
    """Aggregation functions for formulas."""

    COUNT = 'count'
    COUNT_VALUES = 'count_values'
    COUNT_PER_GROUP = 'count_per_group'

    EMPTY = 'empty'
    NOT_EMPTY = 'not_empty'

    CHECKED = 'checked'
    UNCHECKED = 'unchecked'

    PERCENT_EMPTY = 'percent_empty'
    PERCENT_NOT_EMPTY = 'percent_not_empty'
    PERCENT_CHECKED = 'percent_checked'
    PERCENT_PER_GROUP = 'percent_per_group'

    AVERAGE = 'average'
    MIN = 'min'
    MAX = 'max'
    MEDIAN = 'median'
    RANGE = 'range'
    SUM = 'sum'

    DATE_RANGE = 'date_range'
    EARLIEST_DATE = 'earliest_date'
    LATEST_DATE = 'latest_date'

    SHOW_ORIGINAL = 'show_original'
    SHOW_UNIQUE = 'show_unique'
    UNIQUE = 'unique'


class NumberFormat(str, Enum):
    """Number formats for numbers."""

    NUMBER = 'number'
    NUMBER_WITH_COMMAS = 'number_with_commas'
    PERCENT = 'percent'
    DOLLAR = 'dollar'
    CANADIAN_DOLLAR = 'canadian_dollar'
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
