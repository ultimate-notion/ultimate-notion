from __future__ import annotations

from notional import types, user


class User:
    def __init__(self, obj_ref: types.User):
        self.obj_ref: types.User = obj_ref

    def __str__(self):
        return self.name

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        return f"<{cls_name}: '{str(self)}' at {hex(id(self))}>"

    def __eq__(self, other):
        return self.id == other.id

    @property
    def id(self):  # noqa: A003
        return self.obj_ref.id

    @property
    def name(self):
        return self.obj_ref.name

    @property
    def type(self):  # noqa: A003
        return self.obj_ref.type.value

    @property
    def is_person(self) -> bool:
        return isinstance(self.obj_ref, user.Person)

    @property
    def is_bot(self) -> bool:
        return isinstance(self.obj_ref, user.Bot)

    @property
    def avatar_url(self):
        return self.obj_ref.avatar_url

    @property
    def email(self) -> str | None:
        if isinstance(self.obj_ref, user.Person):
            return self.obj_ref.person.email
        else:  # it's a bot without an e-mail
            return None
