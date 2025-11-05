#!/usr/bin/env python3
"""
secrets_utils.py
Smart config loader that automatically detects if it's running in Docker,
and reads from /run/secrets/ if available, otherwise falls back to .env

Usage:
    from src.secrets_utils import get_config
    
    # Same API as python-decouple's config()
    DB_HOST = get_config('DB_HOST')
    DB_PORT = get_config('DB_PORT', default=5432, cast=int)
    USE_SSH = get_config('USE_SSH_TUNNEL', default=False, cast=bool)
"""

import os
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union

try:
    from decouple import config as decouple_config
    HAS_DECOUPLE = True
except ImportError:
    decouple_config = None
    HAS_DECOUPLE = False

T = TypeVar('T')

# Docker Secrets are mounted at /run/secrets/ by default
DOCKER_SECRETS_PATH = Path('/run/secrets')


def _read_docker_secret(secret_name: str) -> Optional[str]:
    """
    Read a Docker secret from the filesystem.
    
    Args:
        secret_name: Name of the secret (will be converted to lowercase with underscores)
    
    Returns:
        Secret value as string, or None if not found
    """
    # Docker secret names use lowercase with underscores
    # e.g., DB_HOST -> db_host
    secret_file = DOCKER_SECRETS_PATH / secret_name.lower()
    
    if secret_file.exists() and secret_file.is_file():
        try:
            # Read and strip whitespace (Docker secrets often have trailing newlines)
            with open(secret_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"Warning: Failed to read Docker secret '{secret_name}': {e}")
            return None
    
    return None


def _is_docker_environment() -> bool:
    """
    Detect if we're running in a Docker container.
    
    Returns:
        True if running in Docker, False otherwise
    """
    # Check for Docker-specific files/environment
    docker_indicators = [
        Path('/.dockerenv').exists(),
        DOCKER_SECRETS_PATH.exists(),
        os.getenv('DOCKER_ENV') == 'true',
    ]
    
    return any(docker_indicators)


# Sentinel value to detect when no default was provided
_UNDEFINED = object()


def get_config(
    key: str,
    default: Any = _UNDEFINED,
    cast: Optional[Callable[[str], T]] = None
) -> Union[T, Any]:
    """
    Get configuration value from Docker Secrets or .env file.
    
    Priority order:
    1. Docker Secret (if running in Docker and secret exists)
    2. Environment variable
    3. .env file (via python-decouple)
    4. Default value
    
    Args:
        key: Configuration key name (e.g., 'DB_HOST', 'SMTP_PORT')
        default: Default value if key is not found (can be None)
        cast: Function to cast the value (e.g., int, bool, float)
    
    Returns:
        Configuration value, cast to appropriate type if specified
    
    Examples:
        >>> DB_HOST = get_config('DB_HOST')
        >>> DB_PORT = get_config('DB_PORT', default=5432, cast=int)
        >>> USE_SSH = get_config('USE_SSH_TUNNEL', default=False, cast=bool)
        >>> OPTIONAL = get_config('OPTIONAL_KEY', default=None)  # None is valid
    """
    value = None
    
    # Try Docker Secret first (if in Docker environment)
    if _is_docker_environment():
        value = _read_docker_secret(key)
        if value is not None:
            # Apply cast if provided
            if cast is not None:
                try:
                    return cast(value)
                except (ValueError, TypeError) as e:
                    print(f"Warning: Failed to cast Docker secret '{key}': {e}")
                    # Fall through to try other methods
                    value = None
            else:
                return value
    
    # Fall back to environment variables and .env file
    if HAS_DECOUPLE:
        try:
            if default is _UNDEFINED:
                # No default provided - let decouple raise UndefinedValueError if missing
                return decouple_config(key, cast=cast)
            else:
                # Default provided (could be None, which is valid)
                return decouple_config(key, default=default, cast=cast)
        except Exception:
            # Silently fall through to environment variables
            # This is expected when running in Docker without .env file
            pass
    
    # Last resort: check environment variables directly
    env_value = os.getenv(key)
    if env_value is not None:
        if cast is not None:
            try:
                return cast(env_value)
            except (ValueError, TypeError):
                pass
        return env_value
    
    # Return default if one was provided (even if it's None)
    if default is not _UNDEFINED:
        return default
    
    # If we get here, no value was found and no default was provided
    raise ValueError(
        f"Configuration key '{key}' not found in Docker Secrets, "
        f"environment variables, or .env file, and no default provided"
    )


def get_ssh_key_path(key_name: str, default_path: str = '', fallback_config_key: str = 'SSH_KEY_PATH') -> str:
    """
    Special handler for SSH keys that may come from Docker Secrets.
    
    If running in Docker with secrets, writes the secret content to a temporary
    file and returns that path. Otherwise returns the configured path.
    
    Args:
        key_name: Name of the secret containing SSH key content (e.g., 'ssh_ubuntu_key_content')
        default_path: Default file path if not using secrets
        fallback_config_key: Config key to check for path (e.g., 'SSH_KEY_PATH')
    
    Returns:
        Path to SSH key file
    """
    if _is_docker_environment():
        secret_content = _read_docker_secret(key_name)
        if secret_content is not None:
            # Write to a temporary location in the container
            import tempfile
            key_file = Path(tempfile.gettempdir()) / f"{key_name}.pem"
            
            # Write the key content
            with open(key_file, 'w', encoding='utf-8') as f:
                f.write(secret_content)
                # Ensure newline at end if not present
                if not secret_content.endswith('\n'):
                    f.write('\n')
            
            # Set appropriate permissions (readable only by owner)
            os.chmod(key_file, 0o400)
            
            return str(key_file)
    
    # Fall back to configured path
    try:
        return get_config(fallback_config_key, default=default_path)
    except:
        return default_path or ''


# Convenience function for boolean configs
def get_bool_config(key: str, default: bool = False) -> bool:
    """
    Get a boolean configuration value.
    
    Args:
        key: Configuration key name
        default: Default value if not found
    
    Returns:
        Boolean value
    """
    return get_config(key, default=default, cast=bool)


# Convenience function for integer configs
def get_int_config(key: str, default: int = 0) -> int:
    """
    Get an integer configuration value.
    
    Args:
        key: Configuration key name
        default: Default value if not found
    
    Returns:
        Integer value
    """
    return get_config(key, default=default, cast=int)


# Convenience function for float configs
def get_float_config(key: str, default: float = 0.0) -> float:
    """
    Get a float configuration value.
    
    Args:
        key: Configuration key name
        default: Default value if not found
    
    Returns:
        Float value
    """
    return get_config(key, default=default, cast=float)
