#!/bin/bash
# Activation script for MCP Server conda environment

# Initialize conda
source $HOME/miniconda3/etc/profile.d/conda.sh

# Activate the mcp_server environment
conda activate mcp_server

echo "✅ Activated conda environment: mcp_server"
echo "Python version: $(python --version)"
echo "Environment path: $(which python)"