# Tomviz Standalone Installer Packaging

This repository builds standalone installers for [Tomviz](https://github.com/OpenChemistry/tomviz) from conda-forge packages.

## Output Formats

| Platform | Format | Notes |
|---|---|---|
| macOS x64 | `.dmg` | Unsigned — sign/notarize internally before distribution |
| macOS ARM | `.dmg` | Unsigned — sign/notarize internally before distribution |
| Windows | `.msi`, `.zip` | MSI is unsigned — sign internally before distribution |
| Linux | `.tar.gz` | |

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
cpack --config CPackConfig.cmake
```

## Publishing to OpenChemistry/tomviz

Releases in this repo are built automatically for every conda-forge update, but they are **not** auto-published to [OpenChemistry/tomviz](https://github.com/OpenChemistry/tomviz). The macOS DMGs and Windows MSI produced by CI are unsigned, and publishing unsigned binaries to the user-facing repo would trigger Gatekeeper/SmartScreen warnings for end users.

Instead, specific releases are hand-picked, signed, and published manually:

1. Pick a release from this repo's GitHub Releases page.
2. Download the macOS DMGs (x64 and ARM) and the Windows MSI.
3. Sign and notarize the DMGs, and sign the MSI, using the internal signing process.
4. Create a matching release on `OpenChemistry/tomviz` and upload the signed DMGs and MSI along with the Linux artifacts from this repo's release.
