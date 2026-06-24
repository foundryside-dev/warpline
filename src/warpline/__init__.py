from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

try:
    # Single source of truth: the version is read from the installed package
    # metadata (pyproject `version`), never a hand-maintained literal — so a
    # release bump can never leave __version__ (and thus --version, the MCP
    # serverInfo, and every envelope's meta.producer.version) stale.
    __version__ = _package_version("warpline")
except PackageNotFoundError:  # pragma: no cover - source tree with no installed dist
    __version__ = "0.0.0+unknown"
