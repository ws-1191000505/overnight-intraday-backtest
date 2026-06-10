from src.data_sources.twelve_data_client import TwelveDataClient


def test_effective_interval_respects_minutely_limit() -> None:
    client = TwelveDataClient(
        api_key="dummy",
        request_interval_seconds=1,
        minutely_limit=8,
        rate_limit_safety_seconds=0.75,
    )
    assert client.request_interval_seconds == 8.25


def test_configured_interval_can_be_more_conservative() -> None:
    client = TwelveDataClient(
        api_key="dummy",
        request_interval_seconds=10,
        minutely_limit=8,
        rate_limit_safety_seconds=0.75,
    )
    assert client.request_interval_seconds == 10
