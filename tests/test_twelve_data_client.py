from src.data_sources.twelve_data_client import TwelveDataClient, _is_no_data_error


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


def test_no_data_error_detection_does_not_hide_auth_errors() -> None:
    assert _is_no_data_error("No data is available on the specified dates")
    assert not _is_no_data_error("Invalid API key")
