# Shared fakes for cuppa unit tests (no compiler / no network).


class FakeEnv(dict):
    """Minimal env with get_option() backed by the dict itself."""

    def get_option(self, name, default=None):
        return self.get(name, default)
