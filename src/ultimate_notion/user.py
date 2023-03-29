from notional import types, user


class User:
    def __init__(self, obj_ref: types.User):
        self.obj_ref: types.User = obj_ref

    @property
    def id(self):
        return self.obj_ref.id

    @property
    def name(self):
        return self.obj_ref.name

    @property
    def type(self):
        return self.obj_ref.type.value

    @property
    def avatar_url(self):
        return self.obj_ref.avatar_url

    @property
    def email(self):
        assert isinstance(self.obj_ref, user.Person), "only a person type has an e-mail"
        return self.obj_ref.person.email
