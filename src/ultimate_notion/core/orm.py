"""Utilities for working with Notion as an ORM.

There are two primary constructs in this module that enable custom type definitions
in Notional: `Property()` and `connected_page()`.
"""

import logging
from typing import Union

from emoji import emojize

from .records import Database, DatabaseRef, Page
from .schema import PropertyObject, RichText
from .text import is_emoji, make_safe_python_name
from .types import EmojiObject, ExternalFile, PropertyValue

_log = logging.getLogger(__name__)


class ConnectedProperty:
    """Contains the information and methods needed for a connected property.

    When created, this object does not have a reference to its parent object.  Before
    this property is accessed for the first time, callers must use `bind()` to set the
    containing object at runtime.
    """

    def __init__(self, name, schema, default=...):
        """Initialize the property wrapper.

        :param name: the name of this property as it appears on Notional

        :param schema: the PropertyObject that defines the type of this property

        :param default: an optional parameter that will return a default value if one
          is not provided by the API
        """

        if name is None or len(name) == 0:
            raise ValueError("Must provide a valid property name")

        if schema is None:
            raise ValueError("Invalid schema; cannot be None")

        self.name = name
        self.default = default
        self.schema = schema
        self.data_type = type(schema)

        if not hasattr(self.data_type, "type") or self.data_type.type is None:
            raise ValueError("Invalid schema; undefined type")

        self.type_name = self.data_type.type

        # this is kind of an ugly way to grab the value type from the schema type...
        # mostly b/c we are using internal knowledge of TypedObject.__typemap__
        if self.type_name not in PropertyValue.__typemap__:
            raise TypeError(f"Invalid schema; missing value type '{self.type_name}'")

        self.value_type = PropertyValue.__typemap__[self.type_name]

    def bind(self, obj):
        """Binds this property to the given object."""

        if not isinstance(obj, ConnectedPage):
            raise TypeError("Properties must be used in a ConnectedPage object")

        # XXX should we do any additional error checking on the object?

        self.parent = obj
        self.page_data = self.parent._notional__page
        self.session = self.parent._notional__session

    def get(self):
        """Return the current value of the property as a python object."""
        _log.debug("fget :: %s [%s]", self.type_name, self.name)

        # TODO raise instead?
        if self.page_data is None:
            return None

        try:
            prop = self.page_data[self.name]
        except AttributeError:
            if self.default == ...:
                raise AttributeError(f"Missing property: '{self.name}'")
            return self.default

        if not isinstance(prop, self.value_type):
            raise TypeError("Type mismatch")

        if hasattr(prop, "Value"):
            return prop.Value

        return prop

    def set(self, value):
        """Set the property to the given value."""
        _log.debug("fset :: %s [%s] => %s", self.type_name, self.name, type(value))

        # TODO raise instead?
        if self.page_data is None:
            return

        if isinstance(value, self.value_type):
            prop = value

        elif hasattr(self.value_type, "__compose__"):
            prop = self.value_type.__compose__(value)

        else:
            raise TypeError(f"Unsupported value type for '{self.type_name}'")

        # update the property on the server (which will refresh the local data)
        self.session.pages.update(self.page_data, **{self.name: prop})

    def delete(self):
        """Delete the value associated with this property."""

        # TODO raise instead?
        if self.page_data is None:
            return

        empty = self.value_type()

        self.session.pages.update(self.page_data, **{self.name: empty})


def Property(name, schema=None, default=...):
    """Define a property for a Notion Page object.

    Internally, this method uses a custom wrapper to manage the property methods.

    :param name: the Notion table property name
    :param schema: the schema that defines this property (default = RichText)
    :param default: a default value when creating new objects
    """

    _log.debug("creating new Property: %s", name)

    if schema is None:
        schema = RichText()

    elif not isinstance(schema, PropertyObject):
        raise TypeError("Invalid data_type; not a PropertyObject")

    cprop = ConnectedProperty(
        name=name,
        schema=schema,
        default=default,
    )

    def fget(self):
        """Return the current value of the property as a python object."""
        cprop.bind(self)
        return cprop.get()

    def fset(self, value):
        """Set the property to the given value."""
        cprop.bind(self)
        cprop.set(value)

    def fdel(self):
        """Delete the value for this property."""
        cprop.bind(self)
        cprop.delete()

    return property(fget, fset, fdel)


class ConnectedPage:
    """Base class for "live" pages via the Notion API.

    All changes are committed in real time.
    """

    def __init__(self, **data):
        """Construct a page from the given data dictionary."""
        self._notional__page = Page(**data) if data else None

    def __init_subclass__(cls, database=None, **kwargs):
        """Register new subclasses of a ConnectedPage."""
        super(cls).__init_subclass__(**kwargs)

        if database is not None:
            cls._notional__database = database

        elif hasattr(cls, "__database__"):
            cls._notional__database = cls.__database__

    @property
    def id(self):
        """Return the ID of this page (if available)."""
        return self._notional__page.id if self._notional__page else None

    @property
    def children(self):
        """Return an iterator for all child blocks of this Page."""

        if self._notional__page is None:
            return []

        return self._notional__session.blocks.children.list(parent=self._notional__page)

    @property
    def cover(self):
        """Return the cover for the Page."""
        return self._notional__page.cover

    @cover.setter
    def cover(self, file):
        """Set the cover for the Page."""
        self._notional__session.pages.set(self._notional__page, cover=file)

    @property
    def icon(self):
        """Return the icon for the Page."""
        return self._notional__page.icon

    @icon.setter
    def icon(self, icon: Union[str, EmojiObject, ExternalFile]):
        """Set the icon for the Page.

        :param icon: may be either a single emoji string or an `EmojiObject`
        """

        if isinstance(icon, str):
            if icon.startswith(":"):
                icon = emojize(icon, language="alias")
            if is_emoji(icon):
                icon = EmojiObject[icon]
            elif icon.startswith("http"):
                icon = ExternalFile[icon]
            else:
                raise ValueError(f"Cannot interpret string `{icon}` as icon")
        elif isinstance(icon, (EmojiObject, ExternalFile)):
            pass
        else:
            raise ValueError("Invalid icon specifier; unsupported type")

        self._notional__session.pages.set(self._notional__page, icon=icon)

    def __iadd__(self, block):
        """Append the given block to this page.

        This operation takes place on the Notion server, causing the page to save
        immediately.
        """

        self.append(block)

        return self

    def append(self, *blocks):
        """Append the given blocks as children of this ConnectedPage.

        This operation takes place on the Notion server, causing the page to update
        immediately.
        """

        if self._notional__page is None:
            raise ValueError("Cannot append blocks; missing page")

        if self._notional__session is None:
            raise ValueError("Cannot append blocks; invalid session")

        _log.debug("appending %d blocks to page :: %s", len(blocks), self._notional__page.id)

        self._notional__session.blocks.children.append(self._notional__page, *blocks)

    @classmethod
    def bind(cls, to_session):
        """Attach this ConnectedPage to the given session.

        Setting this to None will detach the page.
        """

        cls._notional__session = to_session

    @classmethod
    def query(cls):
        """Return a `QueryBuilder` for the custom type."""

        if cls._notional__session is None:
            raise ValueError("Unable to query; invalid session")

        if cls._notional__database is None:
            raise ValueError("Unable to query; invalid database")

        return cls._notional__session.databases.query(cls)

    @classmethod
    def create(cls, **kwargs):
        """Create a new instance of the ConnectedPage type.

        Any properties that support object composition may be defined in `kwargs`.

        This operation takes place on the Notion server, creating the page immediately.

        :param kwargs: the properties to initialize for this object as parameters, i.e.
          `name=value`, where `name` is the attribute in the custom type
          and `value` is a supported type for composing.
        """

        if cls._notional__session is None:
            raise ValueError("Cannot create Page; invalid session")

        if cls._notional__database is None:
            raise ValueError("Cannot create Page; invalid database")

        _log.debug("creating new %s :: %s", cls, cls._notional__database)

        parent = DatabaseRef(database_id=cls._notional__database)

        connected = cls()
        connected._notional__page = cls._notional__session.pages.create(parent=parent)

        # FIXME it would be better to convert properties to a dict and pass to the API,
        # rather than setting them individually here...
        for name, value in kwargs.items():
            setattr(connected, name, value)

        return connected

    @classmethod
    def parse_obj(cls, data):
        """Invoke the class constructor using the structured data.

        Similar to `BaseModel.parse_obj(data)`.
        """
        return cls(**data)


class ConnectedPageFactory:
    """A factory that builds custom types for `ConnectedPage` classes.

    Typically, these generated classes will be extended to form a custom type.
    """

    # TODO consider making this more general purpose (e.g. extend other base objects)

    def __init__(
        self,
        name="CustomBase",
        base=None,
        metaclass=None,
    ):
        """Initialize the `ConnectedPageFactory` with the given parameters.

        :param name: the name of the class generated by this factory;
          defaults to "CustomBase"

        :param base: the class (or tuple of classes) used as the base class for types
          generated by this factory; defaults to `None`

        :param metaclass: the callable metaclass to use for generating new types;
          defaults to `type`
        """

        self.name = name

        if base is None:
            self.bases = (ConnectedPage,)
        elif isinstance(base, tuple):
            self.bases = base
        else:
            self.bases = (base,)

        if metaclass is None:
            self.metaclass = type
        else:
            self.metaclass = metaclass

    def __call__(self, session, database, schema=None):
        """Return a new type from this factory with the given configuration."""

        attrs = {
            "_notional__session": session,
            "_notional__database": database,
        }

        if schema is not None:
            for name, obj in schema.items():
                safe_name = make_safe_python_name(name)
                prop = Property(name, obj)
                attrs[safe_name] = prop

        return self.metaclass(self.name, self.bases, attrs)


def connected_page(session=None, source_db=None, schema=None, cls=None):
    """Return a base class for "connected" pages through the Notion API.

    Subclasses may then inherit from the returned class to define custom ORM types.

    :param session: an active Notional session where the database is hosted

    :param source_db: if provided, the returned class will use the ID and schema of
      this object to initialize the connected page

    :param schema: if provided, the returned class will contain properties according
      to the schema provided; defaults to `None`

    :param cls: the returned class will inherit from the given class, which must be a
      sublass of `ConnectedPage`; defaults to `ConnectedPage`
    """

    if cls is None:
        cls = ConnectedPage

    elif not issubclass(cls, ConnectedPage):
        raise ValueError("'cls' must subclass ConnectedPage")

    if source_db is None:
        dbid = None

    elif not isinstance(source_db, Database):
        raise ValueError("'source_db' must be a Database")

    else:
        if schema is None:
            schema = source_db.properties

        dbid = source_db.id

    factory = ConnectedPageFactory(base=cls)

    return factory(
        session=session,
        database=dbid,
        schema=schema,
    )
