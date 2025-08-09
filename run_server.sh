#!/bin/bash
# Script to run the MCP server with conda environment activated

# Ensure conda is in PATH
export PATH="$HOME/miniconda3/bin:$PATH"

# Initialize conda and activate environment
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate mcp_server

# Run the server
echo "🚀 Starting MCP Server on port 8081..."
python main.py