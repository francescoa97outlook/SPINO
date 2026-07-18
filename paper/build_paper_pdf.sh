#!/bin/bash
#
# Build a local preview of the SPINO JOSS paper.
#
# Uses the official Open Journals toolchain (the openjournals/inara Docker image),
# which is the same one the JOSS review bot runs, so what you get here is what the
# editors will see.
#
#   ./build_paper_pdf.sh              draft PDF (watermark + line numbers, as in review)
#   ./build_paper_pdf.sh --production final PDF, no watermark
#
# Output: paper/paper.pdf

set -euo pipefail

PAPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INARA_IMAGE="openjournals/inara"
# Restrict the output to the PDF. Without this, inara also emits JATS XML into
# paper/jats/, which is only needed by the journal's own publishing pipeline.
INARA_ARGS=("-o" "pdf")
MODE="draft"

while [ $# -gt 0 ]; do
    case "$1" in
        -p|--production)
            INARA_ARGS+=("-p")
            MODE="production"
            shift
            ;;
        -h|--help)
            sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $(basename "${BASH_SOURCE[0]}") [-p|--production]" >&2
            exit 2
            ;;
    esac
done

echo "-----------------------------------------------------"
echo "SPINO JOSS paper build ($MODE)"
echo "Paper directory: $PAPER_DIR"
echo "-----------------------------------------------------"
echo ""

# --- Preflight -------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not installed." >&2
    echo "The JOSS toolchain is distributed as a Docker image; install Docker, or" >&2
    echo "see https://joss.readthedocs.io/en/latest/paper.html for alternatives." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: the Docker daemon is not responding." >&2
    echo "Start it (e.g. 'sudo systemctl start docker') and check that your user can" >&2
    echo "reach it ('docker info' should succeed without sudo)." >&2
    exit 1
fi

missing=0
for f in paper.md paper.bib figures/gui.png figures/output.png; do
    if [ ! -f "$PAPER_DIR/$f" ]; then
        echo "ERROR: missing required file: paper/$f" >&2
        missing=1
    fi
done
[ "$missing" -eq 0 ] || exit 1

echo "Checked: paper.md, paper.bib, and both figures are present."
echo ""

# --- Build -----------------------------------------------------------------

# Remove any stale PDF so a failed build cannot masquerade as a successful one.
rm -f "$PAPER_DIR/paper.pdf"

echo "Pulling/updating $INARA_IMAGE ..."
docker pull "$INARA_IMAGE"
echo ""

echo "Compiling paper.md ..."
docker run --rm \
    --volume "$PAPER_DIR":/data \
    --user "$(id -u):$(id -g)" \
    --env JOURNAL=joss \
    "$INARA_IMAGE" "${INARA_ARGS[@]}" paper.md
echo ""

# --- Verify ----------------------------------------------------------------

if [ ! -f "$PAPER_DIR/paper.pdf" ]; then
    echo "ERROR: the build finished but paper/paper.pdf was not created." >&2
    exit 1
fi

echo "-----------------------------------------------------"
echo "PDF built: $PAPER_DIR/paper.pdf"
echo ""
echo "Check before submitting:"
echo "  - both figures render legibly at page width"
echo "  - no citation shows up as a bare [?]"
echo "  - author, ORCID, and affiliations are correct in the header"
echo "-----------------------------------------------------"
