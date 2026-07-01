class AIServiceError(Exception):
    """Raised by any AI provider adapter; carries an HTTP status code for the view layer."""
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code
