#!/usr/bin/env bash
# Clean Code Reviewer installer
# Usage: curl -sSL https://raw.githubusercontent.com/CleanCodeReviewer/CleanCodeReviewer/main/install.sh | bash

set -e

echo "Installing Clean Code Reviewer..."

# Check for uv first (preferred)
if command -v uv &> /dev/null; then
    echo "Using uv..."
    uv tool install clean-code-reviewer
# Check for pipx
elif command -v pipx &> /dev/null; then
    echo "Using pipx..."
    pipx install clean-code-reviewer
# Fallback to pip with warning
elif command -v pip3 &> /dev/null; then
    echo "Warning: Installing with pip3. Consider using uv or pipx for isolation."
    pip3 install --user clean-code-reviewer
elif command -v pip &> /dev/null; then
    echo "Warning: Installing with pip. Consider using uv or pipx for isolation."
    pip install --user clean-code-reviewer
else
    echo "Error: No Python package manager found."
    echo "Please install uv (https://docs.astral.sh/uv/) or pipx first."
    exit 1
fi

echo ""
echo "Clean Code Reviewer installed!"
echo ""
echo "Get started:"
echo "  ccr init          # Initialize in your project"
echo "  ccr add google/python   # Add rules"
echo "  ccr review src/   # Review code"
