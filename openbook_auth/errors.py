class OryRequestError(Exception):
    def __init__(self, message: str, error: str, status_code: int):
        self.message = message
        self.error = error
        self.status_code = status_code

    def __str__(self) -> str:
        if self.message or self.error:
            return self.message + ": " + self.error + " - status_code: " + str(self.status_code)
        return super().__str__()


class MatrixRequestError(Exception):
    def __init__(self, message: str, error: str, status_code: int):
        self.message = message
        self.error = error
        self.status_code = status_code

    def __str__(self) -> str:
        if self.message or self.error:
            return self.message + ": " + self.error + " - status_code: " + str(self.status_code)
        return super().__str__()
