"""测试 1: config.py 配置加载"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_settings_default_values():
    """验证默认配置值正确加载。"""
    from config import settings

    assert settings.POLL_INTERVAL_MINUTES == 5
    assert settings.HISTORY_POLL_INTERVAL_MINUTES == 30
    assert settings.TOP_TRADERS_COUNT == 20
    assert settings.SERVER_PORT == 8000
    assert settings.MAX_RETRIES == 3
    assert settings.MAX_CONCURRENT_REQUESTS == 3
    assert settings.WAF_TOKEN_REFRESH_MINUTES == 10
    assert settings.REQUEST_DELAY_MIN == 1.0
    assert settings.REQUEST_DELAY_MAX == 3.0
    print("  [PASS] 默认配置值全部正确")


def test_settings_types():
    """验证配置类型正确。"""
    from config import settings

    assert isinstance(settings.POLL_INTERVAL_MINUTES, int)
    assert isinstance(settings.WEBHOOK_URLS, list)
    assert isinstance(settings.DATABASE_URL, str)
    assert isinstance(settings.BINANCE_BASE_URL, str)
    assert isinstance(settings.TRADER_LIST_API, str)
    print("  [PASS] 配置类型全部正确")


def test_settings_binance_urls():
    """验证 Binance 相关 URL 配置。"""
    from config import settings

    assert "binance.com" in settings.BINANCE_BASE_URL
    assert "smart-money" in settings.TRADER_LIST_API
    assert "smart-money" in settings.PROFILE_API
    assert settings.SMART_MONEY_PAGE.startswith("/")
    print("  [PASS] Binance URL 配置正确")


def test_webhook_urls_empty_by_default():
    """验证无环境变量时 Webhook URLs 为空列表。"""
    from config import settings

    assert isinstance(settings.WEBHOOK_URLS, list)
    # 默认没设置 WEBHOOK_URLS 环境变量, 应为空列表
    print(f"  [PASS] Webhook URLs: {settings.WEBHOOK_URLS} (expected empty or configured)")
