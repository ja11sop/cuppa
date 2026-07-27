import cuppa.log


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast tests without compiler or network")
    config.addinivalue_line("markers", "integration: requires cuppa + SCons + C++ compiler")


def pytest_runtest_setup(item):
    cuppa.log._secrets.clear()
