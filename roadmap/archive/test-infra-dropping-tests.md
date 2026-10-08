+++
id = "test-infra-dropping-tests"
title = "Fixed test infra silently dropping tests on a clean install"
filed = 2026-08-03
closed = 2026-08-03
outcome = "shipped"
+++

Test infra was silently dropping tests on a clean install: `pytest-mock`
was missing from `setup.cfg`'s `testing` extra, and the `async_int_to_letter`
fixture in `conftest.py` wasn't decorated for strict-mode `pytest-asyncio`.
Both fixed; added regression tests for the two bugs above
(`test_min.py`, `test_max.py`, `test_exception.py`).
