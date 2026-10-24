from flask.testing import FlaskClient


class InternalServiceTestClient(FlaskClient):
    """Test client para invocar APIs internas como lo hace ServiceClient."""

    def open(self, *args, **kwargs):
        environ_overrides = dict(kwargs.pop("environ_overrides", {}) or {})
        environ_overrides["moova.interno"] = True
        kwargs["environ_overrides"] = environ_overrides
        return super().open(*args, **kwargs)


def internal_test_client(app):
    app.test_client_class = InternalServiceTestClient
    return app.test_client()
