"""Backend package.

The backend intentionally keeps this module lightweight.  Individual services
are imported from their concrete modules so importing ``backend.config`` or
another submodule does not initialize the agent runtime or contact Azure.
"""

__all__: list[str] = []
