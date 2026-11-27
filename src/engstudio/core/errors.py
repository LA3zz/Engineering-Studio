"""Typed error hierarchy. Every error has a stable machine-readable ``code``."""

from __future__ import annotations

from engstudio.core.diagnostics import Diagnostic, SourceLoc


class EngStudioError(Exception):
    """Base class for all errors raised by Engineering Studio."""

    code = "E_GENERIC"

    def to_diagnostic(self, location: SourceLoc | None = None) -> Diagnostic:
        return Diagnostic("error", self.code, str(self), location)


class ValidationError(EngStudioError):
    """Invalid input value or type."""

    code = "E_VALIDATION"


class DimensionError(ValidationError):
    """Array shapes are incompatible for the requested operation."""

    code = "E_DIMENSION"


class UnitError(ValidationError):
    """Unknown or incompatible unit."""

    code = "E_UNIT"


class SingularMatrixError(EngStudioError):
    """Matrix is singular to working precision."""

    code = "E_SINGULAR"

    def __init__(self, message: str = "Matrix is singular to working precision",
                 rcond: float | None = None) -> None:
        if rcond is not None:
            message = f"{message} (rcond = {rcond:.3e})"
        super().__init__(message)
        self.rcond = rcond


class ConvergenceError(EngStudioError):
    """An iterative method failed to converge."""

    code = "E_CONVERGENCE"

    def __init__(self, message: str, iterations: int | None = None,
                 last_estimate: object | None = None) -> None:
        super().__init__(message)
        self.iterations = iterations
        self.last_estimate = last_estimate


class NotSupportedError(EngStudioError):
    """Feature is outside the documented supported subset."""

    code = "E_NOT_SUPPORTED"


class PluginError(EngStudioError):
    """Invalid toolbox/plugin definition or registration."""

    code = "E_PLUGIN"
