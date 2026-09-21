# Setup retry tests

Run from the repository root in an isolated Linux environment. Use Python 3.14
for Core 2026.9.3:

```sh
python -m pip install -r requirements_test.txt
python -m pip check
python -m pytest -q
```

For the declared minimum Core 2026.1.0, use Python 3.13 and
`requirements_minimum_test.txt` in a separate environment. The pinned test
plugin matches each Core version; the Pyvelop commit matches the manifest's
2026.9.1b9 tag. The minimum environment may need a C compiler for dependencies.

The tests execute Home Assistant's native config-entry setup, retry callbacks,
coordinator cleanup and reauthentication dispatch. Mesh transport, service registration,
platform forwarding/unload and the version-display helper are simulated. They
do not contact a router or instantiate entity platforms. Timeout recovery is a
control; the tests do not assert translated timeout metadata on minimum Core.