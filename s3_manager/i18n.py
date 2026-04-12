"""
i18n - Internationalization module for SkyCLI
使用标准库 gettext 实现中英双语支持
"""
import gettext
import os
from pathlib import Path

LOCALEDIR = Path(__file__).parent / "locale"
DEFAULT_LANG = "zh_CN"

_translation = None
_current_lang = DEFAULT_LANG


def set_language(lang: str) -> None:
    """设置全局语言偏好

    Args:
        lang: 语言代码 ("en" 或 "zh_CN")
    """
    global _translation, _current_lang
    _current_lang = lang

    try:
        _translation = gettext.translation(
            "messages",
            localedir=str(LOCALEDIR),
            languages=[lang]
        )
    except FileNotFoundError:
        _translation = gettext.NullTranslations()


def get_language() -> str:
    """获取当前语言设置"""
    return _current_lang


def _(msgid: str) -> str:
    """翻译函数别名

    Args:
        msgid: 英文消息 ID

    Returns:
        翻译后的消息
    """
    if _translation is None:
        set_language(_current_lang)
    return _translation.gettext(msgid)


def _gettext(msgid: str) -> str:
    """翻译函数

    Args:
        msgid: 英文消息 ID

    Returns:
        翻译后的消息
    """
    return _(msgid)


def ngettext(msgid1: str, msgid2: str, n: int) -> str:
    """复数形式翻译函数

    Args:
        msgid1: 单数形式消息
        msgid2: 复数形式消息
        n: 数量

    Returns:
        翻译后的消息
    """
    if _translation is None:
        set_language(_current_lang)
    return _translation.ngettext(msgid1, msgid2, n)


def init_from_config():
    """从配置文件初始化语言设置"""
    try:
        from .skyconfig import config
        default_profile = config.default_profile or "default"
        profiles = config.list_profiles(profile=default_profile, reload=True)

        if profiles:
            profile = profiles[0] if isinstance(profiles[0], dict) else profiles[0].__dict__
            lang = profile.get("language", DEFAULT_LANG)
            set_language(lang)
        else:
            set_language(DEFAULT_LANG)
    except Exception:
        set_language(DEFAULT_LANG)
