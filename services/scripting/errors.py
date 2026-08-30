# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

class FALError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        if self.line:
            return f"Line {self.line}: {self.message}"
        return self.message


class FALSyntaxError(FALError):
    pass


class FALTypeError(FALError):
    pass


class FALRuntimeError(FALError):
    pass


class FALSecurityError(FALError):
    pass
