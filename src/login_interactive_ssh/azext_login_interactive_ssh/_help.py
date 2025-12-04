# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from knack.help_files import helps


helps['login-ssh'] = """
type: command
short-summary: Log in to Azure using SSH tunnel for authentication
long-summary: |
    This command enables Azure CLI interactive login through SSH tunnels by specifying
    a custom port for OAuth redirect. The authentication URL is displayed in the terminal
    for you to copy to your local browser.

    Typical use case:
    1. Create an SSH tunnel forwarding a local port to the remote server
    2. Run this command on the remote server with the tunneled port
    3. The OAuth redirect will use the specified port
    4. Copy the displayed URL to your local browser to complete authentication

examples:
  - name: Login with SSH port forwarding (typical scenario)
    text: |
        # On local machine: Create SSH tunnel
        ssh -L 8400:localhost:8400 user@remote-server

        # On remote machine: Login with custom port
        az login-ssh --port 8400

        # Copy the displayed URL to your local browser
        # Authentication completes and redirects to localhost:8400 (tunneled back to remote)

  - name: Login with custom port and tenant
    text: az login-ssh --port 8400 --tenant contoso.onmicrosoft.com
"""
