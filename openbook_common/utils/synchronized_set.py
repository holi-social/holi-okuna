import threading


class SynchronizedSet:
    def __init__(self):
        self.strings_lock = threading.Lock()
        self.strings = set()

    def add_if_absent(self, string: str) -> bool:
        """
        returns True, if the value was not present and was added.
        returns False, when the value was already present.
        """
        with self.strings_lock:
            if string in self.strings:
                return False
            self.strings.add(string)
            return True

    def add(self, string: str) -> None:
        with self.strings_lock:
            self.strings.add(string)

    def remove(self, string: str) -> None:
        with self.strings_lock:
            self.strings.discard(string)

    def __contains__(self, key) -> bool:
        with self.strings_lock:
            return key in self.strings
