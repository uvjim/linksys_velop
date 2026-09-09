# Setup lifecycle tests

Run from the repository root in a Linux virtual environment. The tests exercise
Home Assistant's config-entry setup, retry scheduler, coordinator cleanup and
reauthentication with simulated mesh transport and platform boundaries. They do
not connect to a router or instantiate entity platforms.

For the declared minimum, use Python 3.13:

```sh
python -m pip install -r requirements_minimum_test.txt
python -m pip check
python -m pytest -q
```

For Core 2026.9.1, use Python 3.14 and `requirements_test.txt` instead. Use a
separate environment for each lane. The pinned test plugin selects the matching
Core version; the SSDP dependency matches that Core version's manifest. The
minimum lane needs a C compiler to build its pinned `lru-dict` dependency.

The `Tests` workflow runs these two lanes for affected pull requests. Passing
tests establish the synthetic lifecycle contract, not real-device behavior.
