Microsoft Azure CLI 'login-interactive-ssh' Extension
=====================================================

This extension adds the ``az login-ssh`` command to Azure CLI, enabling interactive authentication through SSH tunnels.

Overview
--------

When working on remote servers via SSH, the standard ``az login`` command attempts to open a web browser for authentication, which doesn't work in headless environments. This extension solves this problem by:

1. **Custom OAuth Redirect Port**: Specify a port for the OAuth redirect URL that you can forward through SSH
2. **URL Display**: Display the authentication URL in the terminal instead of attempting to open a browser
3. **SSH Tunnel Support**: Designed specifically for SSH port forwarding scenarios

Understanding the OIDC Authentication Flow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Azure CLI uses the **OpenID Connect (OIDC)** protocol for interactive authentication. Here's how it works:

1. **Authentication Request**: Azure CLI generates a unique authentication URL and directs you to sign in via Microsoft's identity platform
2. **User Authentication**: You sign in through your web browser and approve the authentication request
3. **Redirect with Token**: After successful authentication, Microsoft's identity platform redirects your browser to a **localhost callback URL** with an authorization code
4. **Token Exchange**: Azure CLI listens on localhost at the redirect URL, receives the authorization code, and exchanges it for access tokens

**The Critical Requirement**: A local web server must be listening on ``localhost:<port>`` on the machine where the link is opened to receive the OAuth redirect and capture the authorization code.

The SSH Tunnel Solution
~~~~~~~~~~~~~~~~~~~~~~~~

On a remote server accessed via SSH:

- **Problem**: The client is listening on ``localhost:<port>`` on the remote server, but your web browser is on your local machine
- **Solution**: SSH port forwarding creates a tunnel that forwards traffic from your local ``localhost:<port>`` to the remote server's ``localhost:<port>``

**How it works step-by-step:**

1. You create an SSH tunnel: ``ssh -L 8400:localhost:8400 user@remote-server``
2. On the remote server, you run: ``az login-ssh --port 8400``
3. Azure CLI on the remote server starts listening on ``localhost:8400``
4. You copy the displayed authentication URL to your **local browser**
5. You authenticate with Microsoft
6. Microsoft redirects to ``http://localhost:8400/...`` (your local machine)
7. The SSH tunnel forwards this request through to the remote server's ``localhost:8400``
8. Azure CLI on the remote server receives the authorization code and completes the login

**Visual Flow**:

.. code-block:: text

    Local Machine                SSH Tunnel              Remote Server
    ┌──────────┐                                        ┌──────────┐
    │ Browser  │─┐                                      │ Azure CLI│
    │ at :8400 │ │                                      │ at :8400 │
    └──────────┘ │                                      └──────────┘
                 │                                            ▲
                 │      ╔═══════════════════╗                 │
                 └─────>║ SSH Port Forward  ║─────────────────┘
                        ║ -L 8400:localhost:8400
                        ╚═══════════════════╝

This extension makes this possible by:

- Allowing you to **specify the exact port** (e.g., 8400) instead of using a random port
- **Displaying the authentication URL** in the terminal so you can copy it to your local browser
- Ensuring the remote Azure CLI listens on the **correct port** that matches your SSH tunnel

Installation
------------

Install the extension from a wheel file:

.. code-block:: bash

    az extension add --source login_interactive_ssh-0.1.0-py3-none-any.whl

Usage
-----

Basic Command
~~~~~~~~~~~~~

.. code-block:: bash

    az login-ssh --port <PORT>

The ``--port`` argument is required and specifies which port to use for the OAuth redirect URL.

SSH Tunnel Scenario
~~~~~~~~~~~~~~~~~~~

This is the primary use case for this extension:

.. code-block:: bash

    # On your local machine: Create SSH tunnel
    ssh -L 8400:localhost:8400 user@remote-server

    # On the remote server: Login with the tunneled port
    az login-ssh --port 8400

    # The authentication URL is displayed in the terminal
    # Copy it to your local browser
    # After authentication, the redirect goes to localhost:8400
    # This redirects through the SSH tunnel back to the remote server

Arguments
~~~~~~~~~

Required Arguments:
  ``--port``, ``-p``
    Port for OAuth redirect (1024-65535). Must match the port forwarded via SSH.

Optional Arguments:
  ``--tenant``, ``-t``
    The AAD tenant. Must be provided for Microsoft Account logins.

Examples
--------

Example 1: Standard SSH Tunnel Login
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Step 1: Create SSH tunnel (on local machine)
    ssh -L 8400:localhost:8400 user@remote-server

    # Step 2: Login on remote server
    az login-ssh --port 8400

    # Step 3: Copy the displayed URL to your local browser
    # Step 4: Complete authentication in browser
    # Step 5: The OAuth redirect goes to localhost:8400 (tunneled to remote)

Example 2: Login with Specific Tenant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    az login-ssh --port 8400 --tenant contoso.onmicrosoft.com

How It Works
------------

The extension works by patching Azure CLI's authentication flow:

1. **MSAL Port Injection**: Patches the MSAL (Microsoft Authentication Library) to use your specified port instead of a random ephemeral port
2. **Browser Override**: Replaces browser opening with URL display in the terminal
3. **HTTP Cache Cleanup**: Automatically cleans up corrupted MSAL HTTP cache files to avoid compatibility issues

Technical Details
-----------------

**Port Validation**
  - Port must be between 1024 and 65535 (non-privileged range)
  - Port must be available (not already in use)
  - Clear error messages if validation fails
  - **Important**: After a successful login, the port enters TCP TIME_WAIT state and cannot be reused for approximately 60 seconds. Use a different port if you need to login again immediately.

**MSAL Compatibility**
  - Automatically disables MSAL HTTP cache to avoid serialization issues
  - Removes corrupted cache files before login
  - Compatible with Azure CLI 2.30.0+

**Security Considerations**
  - All patches are applied temporarily and cleaned up after login
  - No permanent modifications to Azure CLI or MSAL
  - Standard Azure authentication flow is used

Troubleshooting
---------------

**"Port is not available" Error**
  This error occurs when the port is already in use or in TCP TIME_WAIT state.

  **Common Cause - TCP TIME_WAIT State:**
    After a successful login, the TCP connection enters TIME_WAIT state, which prevents the port from being reused for approximately **60 seconds**. This is normal TCP/IP behavior to ensure reliable connection cleanup.

  **Solutions:**

  1. **Use a different port** (recommended): ``az login-ssh --port 8401``
  2. **Wait 60 seconds**: Allow the TIME_WAIT period to expire, then retry with the same port
  3. **Check for other processes**: Verify nothing else is using the port

  **Checking port status:**

  .. code-block:: bash

      # Linux/Mac - Check if port is in use
      lsof -i :8400

      # Linux/Mac - Check for TIME_WAIT state
      netstat -an | grep 8400 | grep TIME_WAIT

      # Windows - Check if port is in use
      netstat -ano | findstr :8400

      # Windows - Check for TIME_WAIT state
      netstat -ano | findstr :8400 | findstr TIME_WAIT

**"Login failed" Error**
  Try removing the MSAL cache manually:

  .. code-block:: bash

      rm -f ~/.azure/msal_http_cache.bin
      rm -f ~/.azure/msal_token_cache

**SSH Tunnel Not Working**
  Verify the SSH tunnel is active:

  .. code-block:: bash

      # On local machine, check for listening port
      netstat -an | grep 8400

  Ensure you're forwarding the correct port in both directions:

  .. code-block:: bash

      ssh -L 8400:localhost:8400 user@remote-server

Comparison with Standard ``az login``
--------------------------------------

+---------------------------+---------------------+------------------------+
| Feature                   | ``az login``        | ``az login-ssh``       |
+===========================+=====================+========================+
| Browser opening           | Automatic           | Displays URL           |
+---------------------------+---------------------+------------------------+
| OAuth redirect port       | Random (ephemeral)  | User-specified         |
+---------------------------+---------------------+------------------------+
| SSH tunnel support        | No                  | Yes (primary use case) |
+---------------------------+---------------------+------------------------+
| Remote server friendly    | No                  | Yes                    |
+---------------------------+---------------------+------------------------+

Uninstallation
--------------

.. code-block:: bash

    az extension remove --name login-interactive-ssh

Related Commands
----------------

- ``az login`` - Standard Azure CLI login command
- ``az account`` - Manage Azure subscriptions
- ``az logout`` - Log out from Azure

Support
-------

This is a community extension. For issues or feature requests, please contact the extension maintainer.

License
-------

MIT License

Copyright (c) Microsoft Corporation. All rights reserved.
