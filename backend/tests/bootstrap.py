"""在导入应用前隔离测试配置，禁用真实密钥、日志落盘及本地环境加载。"""

import os
from contextlib import contextmanager
from tempfile import TemporaryDirectory

from pytest import MonkeyPatch


@contextmanager
def configure():
    with (
        MonkeyPatch.context() as patches,
        TemporaryDirectory(prefix="data-agent-tests-") as directory,
    ):
        for name in list(os.environ):
            if name.startswith("DATA_AGENT_") or name == "DEEPSEEK_API_KEY":
                patches.delenv(name)
        patches.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
        from app.core.config.app_config import app_config

        patches.setattr(app_config.logging.file, "enable", False)
        patches.setattr(app_config.logging.console, "enable", False)
        patches.setattr(app_config.llm, "api_key", "test-only")
        import jieba

        patches.setattr(jieba.dt, "tmp_dir", directory)
        yield
