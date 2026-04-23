# Tomviz Standalone Installer Packaging

This repository builds standalone installers for [Tomviz](https://github.com/OpenChemistry/tomviz) from conda-forge packages.

## Output Formats

| Platform | Format | Notes |
|---|---|---|
| macOS x64 | `.dmg` | Unsigned — sign/notarize internally before distribution |
| macOS ARM | `.dmg` | Unsigned — sign/notarize internally before distribution |
| Windows | `.msi`, `.zip` | |
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

## Configuration

### Publishing to OpenChemistry/tomviz

To also publish releases to the main tomviz repo:

1. Create a PAT with `contents:write` permission on `OpenChemistry/tomviz`
2. Add it as a repository secret named `TOMVIZ_RELEASE_TOKEN`
3. Set the repository variable `PUBLISH_TO_TOMVIZ_REPO` to `true`

### macOS Signing

The CI produces unsigned DMGs. To sign and notarize:

1. Download the DMG from the GitHub Release
2. Sign and notarize using your internal process
3. Re-upload the signed DMG to the release
