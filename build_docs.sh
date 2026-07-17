#!/bin/bash

echo "-----------------------------------------------------"
echo "BASH DEBUG: Current Working Directory: $(pwd)"
echo "BASH DEBUG: Listing files in current directory:"
ls -F
echo "-----------------------------------------------------"

# Put the src/ layout on PYTHONPATH so autodoc can import the 'spino' package.
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
echo "BASH DEBUG: PYTHONPATH is now: $PYTHONPATH"
echo "Generating SPINO documentation..."
echo ""

# Go to docs directory
cd docs

# Check and install documentation dependencies if needed
echo "Checking documentation dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
    echo "   Dependencies checked"
else
    echo "   Warning: requirements.txt not found"
fi
echo ""

# Regenerate API RST files from source code docstrings
echo "Scanning SPINO modules with sphinx-apidoc..."
sphinx-apidoc -f -e -o source/ ../src/spino --force --separate
echo "   RST files generated"
echo ""

echo "Forcing maxdepth to 10 in all RST files..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS version
    find source/ -name "*.rst" -exec sed -i '' 's/:maxdepth: 4/:maxdepth: 10/g' {} +
else
    # Linux/WSL version
    find source/ -name "*.rst" -exec sed -i 's/:maxdepth: 4/:maxdepth: 10/g' {} +
fi
# ---------------------------------

# Build HTML documentation (build once, then inspect the captured log).
# Building twice races on build/html/searchindex.js.tmp and can fail spuriously.
echo "Building HTML documentation..."
make clean
BUILD_LOG=$(make html 2>&1)
echo "$BUILD_LOG"
echo ""

# Check for warnings in the captured build log
WARNINGS=$(echo "$BUILD_LOG" | grep -i warning | wc -l)
if [ "$WARNINGS" -gt 0 ]; then
    echo "Build completed with $WARNINGS warning(s)"
    echo "   Run 'make html 2>&1 | grep -i warning' to see details"
else
    echo "Documentation built successfully with no warnings!"
fi
echo ""

echo "Documentation generated at: docs/build/html/index.html"
echo ""
echo "To view the documentation:"
echo "  - Open docs/build/html/index.html in your browser"
echo "  - Or run: cd docs && make serve"
echo ""
