# Re-export from the nested baml_client package
from baml_client.baml_client import b, types, stream_types, tracing, config, watchers, reset_baml_env_vars

# Make submodules accessible
__all__ = ['b', 'types', 'stream_types', 'tracing', 'config', 'watchers', 'reset_baml_env_vars']
