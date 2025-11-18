# Third-Party Notices

This project vendors certain third-party components to provide a stable and reproducible environment for Chinese futures trading.

## vnpy-ctp 6.7.7.2

- **Name**: vnpy_ctp
- **Version**: 6.7.7.2
- **Upstream Repository**: https://github.com/vnpy/vnpy_ctp/
- **License**: MIT (see `third_party/vnpy_ctp-6.7.7.2/LICENSE`)
- **Location in this repository**: `third_party/vnpy_ctp-6.7.7.2/`
- **Modifications**: None. The source code is vendored as-is from upstream.

When installing CherryQuant, `vnpy-ctp` is built locally from this vendored source via its own `pyproject.toml` (meson-python + meson + pybind11).
