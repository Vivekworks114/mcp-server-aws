"""Minimal runtime entry point for stateless AgentCore agents"""
import os
import sys

# Import the stateless agent (company-specific code will be injected)
from company_agent_stateless import app

if __name__ == "__main__":
    # Run the AgentCore app
    # The app.entrypoint decorator handles the Bedrock AgentCore runtime interface
    app.run()
