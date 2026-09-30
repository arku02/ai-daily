import tomllib
from pathlib import Path

DEFAULT_PATH = Path("sources.toml")


class ConfigError(Exception):
    pass


def load(path=DEFAULT_PATH):
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"找不到設定檔 {path}")
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path} 格式錯誤：{e}") from None
