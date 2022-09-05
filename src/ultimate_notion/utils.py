"""Additional utilities that fit nowhere else"""


# ToDo: Maybe move this to core.types
class slist(list):
    """A list that holds often only a single element"""

    def item(self):
        if len(self) == 1:
            return self[0]
        elif len(self) == 0:
            msg = "list is empty"
        else:
            msg = f"list of {type(self[0]).__name__} has more than one element"
        raise ValueError(msg)
