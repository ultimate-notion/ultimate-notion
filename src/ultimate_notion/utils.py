"""Additional utilities that fit nowhere else"""


class slist(list):
    """A list that holds often only a single element"""

    def item(self):
        if len(self) == 1:
            return self[0]
        elif len(self) == 0:
            raise ValueError("list is empty")
        else:
            raise ValueError(f"list has more than one element of type {type(self[0])}")
