class DatabaseBusyError(Exception):
    """数据库忙异常：BEGIN IMMEDIATE 在多次重试后仍无法获取锁。"""

    def __init__(self, message: str = "数据库繁忙，请稍后重试", retry_after_ms: int = 700):
        super().__init__(message)
        self.message = message
        self.retry_after_ms = retry_after_ms

    def to_dict(self):
        return {
            "message": self.message,
            "retry_after_ms": self.retry_after_ms,
        }
