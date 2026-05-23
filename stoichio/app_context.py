"""Explicit dependency container for Streamlit page modules."""

from types import SimpleNamespace


class AppContext(SimpleNamespace):
    """Names shared from the app shell into page renderers."""

    def require(self, *names):
        missing = [name for name in names if not hasattr(self, name)]
        if missing:
            raise AttributeError(f"AppContext missing: {', '.join(missing)}")
        return {name: getattr(self, name) for name in names}
