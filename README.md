# Tomviz Standalone Installer Packaging

This repository builds standalone installers for [Tomviz](https://github.com/OpenChemistry/tomviz) from conda-forge packages.

## Output Formats

| Platform | Format | Notes |
|---|---|---|
| macOS x64 | `.dmg` | Unsigned — sign/notarize internally before distribution |
| macOS ARM | `.dmg` | Unsigned — sign/notarize internally before distribution |
| Windows | `.msi`, `.zip` | MSI is unsigned — sign internally before distribution |
| Linux | `.tar.gz` | Relocatable bundle, extract anywhere |
| Linux (RHEL8/9) | `.rpm` | Installs to `/opt/tomviz`; relocatable via `--prefix` |
| Linux | `.flatpak` | Single-file bundle, `org.freedesktop.Platform` runtime |

All Linux formats wrap the **same** relocatable conda-forge bundle (`package.py`
+ `conda-pack`), so they stay in lockstep: the `.tar.gz` is the raw bundle, the
`.rpm` drops it into `/opt/tomviz` with desktop integration, and the `.flatpak`
copies it into the sandbox's `/app`.

## How It Works

1. **Check**: A scheduled GitHub Action polls conda-forge every 6 hours for new tomviz releases
2. **Build**: When a new version is detected, it creates a conda environment with tomviz, uses `conda-pack` to make it relocatable, and wraps it in platform-specific bundles
3. **Release**: Uploads installers as GitHub Releases

## Manual Build

```bash
cd packaging
conda env create -f environment.yml
conda activate tomviz-package
python package.py --tomviz-version 2.3.1
cpack --config CPackConfig.cmake          # .tar.gz / .dmg / .msi
```

### Linux RPM and Flatpak

Both consume the bundle staged by `package.py` (`_build/install/tomviz`):

```bash
cd packaging
python package.py --tomviz-version 2.3.1 --python-version 3.13

# RPM (relocatable, installs to /opt/tomviz)
bash linux/build_rpm.sh --staged _build/install --version 2.3.1 --out _build

# Flatpak (single-file bundle)
bash flatpak/build_flatpak.sh --staged _build/install --version 2.3.1 --out _build
```

The committed `linux/tomviz.spec` and `flatpak/org.tomviz.Tomviz.yaml` are the
configuration files required to rebuild each package (per the NSLS-II SOW).

**Build + test locally via Docker** (handles RHEL containers / flatpak sandbox;
uses `linux/amd64` emulation on Apple Silicon):

```bash
bash packaging/linux/build_and_test_rpm_local.sh 2.3.1 3.13       # RPM on Rocky 8 + 9
bash packaging/flatpak/build_and_test_flatpak_local.sh 2.3.1 3.13 # Flatpak smoke test
```

Both mirror the CI tests: structural verification, install, headless smoke test
under software GL, and (for the RPM) a relocation test at a non-default prefix.

## Publishing to OpenChemistry/tomviz

Releases in this repo are built automatically for every conda-forge update, but they are **not** auto-published to [OpenChemistry/tomviz](https://github.com/OpenChemistry/tomviz). The macOS DMGs and Windows MSI produced by CI are unsigned, and publishing unsigned binaries to the user-facing repo would trigger Gatekeeper/SmartScreen warnings for end users.

Instead, specific releases are hand-picked, signed, and published manually:

1. Pick a release from this repo's GitHub Releases page.
2. Download the macOS DMGs (x64 and ARM) and the Windows MSI.
3. Sign and notarize the DMGs, and sign the MSI, using the internal signing process.
4. Create a matching release on `OpenChemistry/tomviz` and upload the signed DMGs and MSI along with the Linux artifacts from this repo's release.
