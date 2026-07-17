#!/bin/bash

# --- PRE-FLIGHT CHECK ---
echo "=========================================================="
echo " PRE-RELEASE CHECKLIST"
echo "=========================================================="
echo "1. Have you bumped '__version__' in 'src/spino/__init__.py'?"
echo "   (single source of truth; pyproject reads it dynamically)"
echo "2. Have you updated the version/badges in 'README.md'?"
echo "3. Have you committed and pushed all changes to GitHub?"
echo "4. Is the CHANGELOG updated (if present)?"
echo "5. Have you tagged the release (git tag vX.Y.Z)?"
echo "=========================================================="

read -p "Are you sure you want to proceed with the release? (y/n): " confirm

if [[ $confirm != "y" ]]; then
    echo "Release aborted. Check your files and try again."
    exit 1
fi

# --- PYPI BUILD & UPLOAD ---
echo "Cleaning old distributions..."
rm -rf dist/ build/ *.egg-info src/*.egg-info

echo "Building the package..."
python -m build

echo "Checking the built distributions..."
python -m twine check dist/*

echo "Uploading to PyPI..."
python -m twine upload dist/* --verbose
