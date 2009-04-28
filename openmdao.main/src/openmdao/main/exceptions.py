

"""
Exception classes for OpenMDAO
"""

#public symbols
__all__ = [
    'ConstraintError',
    'CircularDependencyError',
    'RunFailed',
    'RunInterrupted',
    'RunStopped']

__version__ = "0.1"


class ConstraintError(ValueError):
    """Raised when a constraint is violated."""
    def __init__(self, msg):
        super(ConstraintError, self).__init__(msg)
        
class CircularDependencyError(RuntimeError):
    """Raised when a circular dependency occurs."""
    def __init__(self, msg):
        super(RuntimeError, self).__init__(msg)
        
class RunFailed(RuntimeError):
    """Raised when run() failed for some reason."""
    def __init__(self, msg):
        super(RunFailed, self).__init__(msg)

class RunInterrupted(RuntimeError):
    """Raised when run() was interrupted, implying an inconsistent state."""
    def __init__(self, msg):
        super(RunInterrupted, self).__init__(msg)

class RunStopped(RuntimeError):
    """Raised when run() was stopped, implying a consistent state but
    not necessarily reflecting input values."""
    def __init__(self, msg):
        super(RunStopped, self).__init__(msg)

