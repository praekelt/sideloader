def pytest_configure(config):
    import sys
    from twisted.python import log
    # NOTE: This is necessary for useful failure output in pytest, but is a
    #       problem when running these tests with trial.
    log.startLogging(sys.stdout, setStdout=False)
