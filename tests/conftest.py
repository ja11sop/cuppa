import cuppa.log


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast tests without compiler or network")
    config.addinivalue_line("markers", "integration: requires cuppa + SCons + C++ compiler")
    config.addinivalue_line(
        "markers",
        "serial: run under local_gate --serial-integration (xdist escape hatch)",
    )


def pytest_runtest_setup(item):
    cuppa.log._secrets.clear()
