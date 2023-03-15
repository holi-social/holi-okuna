class OryRequestError(Exception):
    def __init__(self, message: str, error: str, status_code: int):
        self.message = message
        self.error = error
        self.status_code = status_code

    def __str__(self) -> str:
        if self.message:
            return self.message
        return super().__str__()
