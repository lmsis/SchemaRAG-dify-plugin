import os

from dify_plugin import DifyPluginEnv, Plugin

# Large schema builds (reflect + many DISTINCT) need a long window; override with env.
_DEFAULT_TIMEOUT_SEC = 14400  # 4 hours
_MAX_TIMEOUT = int(
    os.environ.get("DIFY_PLUGIN_MAX_REQUEST_TIMEOUT", str(_DEFAULT_TIMEOUT_SEC))
)

plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=_MAX_TIMEOUT))

if __name__ == "__main__":
    plugin.run()
