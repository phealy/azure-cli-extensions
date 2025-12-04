# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import socket
import time
import sys
from contextlib import ExitStack
from unittest.mock import patch
from azure.cli.core.util import CLIError


def _get_time_wait_timeout():
    """
    Get the TIME_WAIT timeout from the system

    Returns:
        int: Timeout in seconds (60 if unable to determine)
    """
    import os
    try:
        # On Linux, read from /proc/sys/net/ipv4/tcp_fin_timeout
        if os.path.exists('/proc/sys/net/ipv4/tcp_fin_timeout'):
            with open('/proc/sys/net/ipv4/tcp_fin_timeout', 'r') as f:
                return int(f.read().strip())
    except (OSError, ValueError):
        pass
    # Default TIME_WAIT timeout (2 * MSL, typically 60 seconds)
    return 60


def check_port_time_wait(port):
    """
    Check if a port is in TIME_WAIT state using psutil

    Args:
        port: Port number to check

    Returns:
        Tuple of (is_time_wait, remaining_seconds)
        - is_time_wait: True if port is in TIME_WAIT state, False otherwise
        - remaining_seconds: Estimated seconds remaining in TIME_WAIT (None if unknown)
    """
    try:
        import psutil

        # Check all network connections for TIME_WAIT state on this port
        for conn in psutil.net_connections(kind='tcp'):
            # Check if this connection involves our port (local or remote)
            if conn.laddr.port == port or (conn.raddr and conn.raddr.port == port):
                # Check if it's in TIME_WAIT status
                if conn.status == 'TIME_WAIT':
                    remaining = _get_time_wait_timeout()
                    return (True, remaining)

        return (False, None)
    except ImportError:
        # psutil not available, can't check TIME_WAIT
        return (False, None)
    except (PermissionError, OSError):
        # Can't access connection information, assume not TIME_WAIT
        return (False, None)


def validate_port_available(port):
    """
    Check if a port is available for binding

    Args:
        port: Port number to check

    Returns:
        True if available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            return True
    except OSError:
        return False


def validate_port(port):
    """
    Validate port number and wait if in TIME_WAIT state

    Args:
        port: Port number to validate

    Raises:
        CLIError: If validation fails
        KeyboardInterrupt: If user cancels during TIME_WAIT countdown
    """
    if not (1024 <= port <= 65535):
        raise CLIError(
            f'Invalid port number: {port}. '
            f'Port must be between 1024 and 65535.'
        )

    if not validate_port_available(port):
        # Check if it's in TIME_WAIT state
        is_time_wait, wait_seconds = check_port_time_wait(port)

        if is_time_wait:
            # Port is in TIME_WAIT - wait with countdown
            # Use system timeout if available, otherwise default to 60
            if wait_seconds is None:
                wait_seconds = 60

            print(f'\nPort {port} is in TIME_WAIT state (from a recent login).', file=sys.stderr)
            print(f'Waiting up to {wait_seconds} seconds for the port to become available...', file=sys.stderr)
            print('Press Ctrl+C to cancel and use a different port instead.\n', file=sys.stderr)

            try:
                for remaining in range(wait_seconds, 0, -1):
                    # Check if port is now available
                    if validate_port_available(port):
                        print(f'\nPort {port} is now available!', file=sys.stderr)
                        return

                    # Show countdown
                    print(f'\rWaiting... {remaining} seconds remaining', end='', file=sys.stderr)
                    sys.stderr.flush()
                    time.sleep(1)

                # Final check after waiting
                print('\r' + ' ' * 50 + '\r', end='', file=sys.stderr)  # Clear the line
                if validate_port_available(port):
                    print(f'Port {port} is now available!', file=sys.stderr)
                    return

                raise CLIError(
                    f'\nPort {port} is still not available after waiting. '
                    f'Try using a different port (e.g., --port {port + 1}).'
                )

            except KeyboardInterrupt:
                print('\n\nLogin cancelled by user.', file=sys.stderr)
                raise CLIError(
                    f'Login cancelled. Try using a different port (e.g., --port {port + 1}).'
                )
        else:
            # Port is in use by another process
            raise CLIError(
                f'Port {port} is not available. '
                f'Another process may be using this port. '
                f'Try using a different port (e.g., --port {port + 1}) or check with: '
                f'lsof -i :{port} (Linux/Mac) or netstat -ano | findstr :{port} (Windows)'
            )


def create_webbrowser_patches():
    """
    Create patches for webbrowser module to display URL instead of opening browser

    Returns:
        List of patch objects
    """
    def patched_open(url, new=0, autoraise=True):  # pylint: disable=unused-argument
        """Display URL in terminal instead of opening browser"""
        print(f'\n{"=" * 70}')
        print('To sign in, use a web browser to open the page:')
        print(f'{"=" * 70}')
        print(url)
        print(f'{"=" * 70}\n')
        return True

    def patched_get(using=None):  # pylint: disable=unused-argument
        """Return a mock browser that displays URL"""
        class MockBrowser:  # pylint: disable=too-few-public-methods
            name = "url_display"

            def open(self, url, new=0, autoraise=True):
                return patched_open(url, new, autoraise)

        return MockBrowser()

    return [
        patch('webbrowser.open', patched_open),
        patch('webbrowser.get', patched_get)
    ]


def create_can_launch_browser_patch():
    """
    Create patch for can_launch_browser to always return True

    Returns:
        Patch object
    """
    return patch('azure.cli.core.util.can_launch_browser', lambda: True)


def login_ssh(cmd, oidc_redirect_port, tenant=None):
    """
    Login to Azure with SSH tunnel support

    Args:
        cmd: CLI command context
        oidc_redirect_port: Port for OAuth redirect
        tenant: AAD tenant ID

    Returns:
        Result from login command
    """
    import os
    from pathlib import Path
    from azure.cli.command_modules.profile.custom import login as original_login

    # Validate port
    validate_port(oidc_redirect_port)

    # Remove corrupted MSAL HTTP cache to avoid pickle/serialization issues
    # This is a workaround for known MSAL compatibility issues
    msal_http_cache = Path.home() / '.azure' / 'msal_http_cache.bin'
    if msal_http_cache.exists():
        try:
            msal_http_cache.unlink()
        except (OSError, PermissionError):
            pass  # Ignore errors if we can't delete it

    # Disable MSAL HTTP cache to avoid future issues
    original_use_http_cache = os.environ.get('AZURE_CLI_DISABLE_MSAL_HTTP_CACHE')
    os.environ['AZURE_CLI_DISABLE_MSAL_HTTP_CACHE'] = '1'

    try:
        # Collect patches to apply
        patches = []

        # MSAL port patch (always applied)
        try:
            from msal import PublicClientApplication

            # Store original method
            original_acquire = PublicClientApplication.acquire_token_interactive

            # Create patched method that injects the port
            def patched_acquire(self, *args, **kwargs):
                kwargs['port'] = oidc_redirect_port
                return original_acquire(self, *args, **kwargs)

            patches.append(
                patch.object(PublicClientApplication, 'acquire_token_interactive', patched_acquire)
            )
        except ImportError:
            raise CLIError('MSAL library not found. Cannot apply port patch.')

        # Webbrowser patches (always display URL instead of opening browser)
        patches.extend(create_webbrowser_patches())

        # can_launch_browser patch
        try:
            patches.append(create_can_launch_browser_patch())
        except (ImportError, AttributeError):
            # If can_launch_browser doesn't exist, skip this patch
            pass

        # Apply all patches using ExitStack for clean management
        try:
            with ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)

                # Call original login with patches active
                # Only pass tenant if provided
                kwargs = {}
                if tenant:
                    kwargs['tenant'] = tenant

                return original_login(cmd, **kwargs)

        except Exception as e:
            # Re-raise as CLIError for proper formatting
            if isinstance(e, CLIError):
                raise
            raise CLIError(f'Login failed: {str(e)}')

    finally:
        # Restore original environment variable
        if original_use_http_cache is None:
            os.environ.pop('AZURE_CLI_DISABLE_MSAL_HTTP_CACHE', None)
        else:
            os.environ['AZURE_CLI_DISABLE_MSAL_HTTP_CACHE'] = original_use_http_cache
