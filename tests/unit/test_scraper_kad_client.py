"""Tests for KAD client."""

import pytest
from httpx import Response
from pytest_mock import MockerFixture

from src.core.exceptions import ConnectionException, ScraperException
from src.scraper.kad_client import KadArbitrClient


@pytest.mark.asyncio
async def test_client_initialization() -> None:
    """Test client initialization."""
    client = KadArbitrClient()

    assert client.base_url == "https://kad.arbitr.ru"
    assert client.timeout == 30
    assert client.max_retries == 3


@pytest.mark.asyncio
async def test_client_context_manager() -> None:
    """Test client as async context manager."""
    async with KadArbitrClient() as client:
        await client._ensure_client()
        assert client._client is not None

    assert client._client is None


@pytest.mark.asyncio
async def test_search_cases_basic(mocker: MockerFixture) -> None:
    """Test basic case search."""
    mock_response = {
        "Result": {
            "TotalCount": 1,
            "Items": [
                {
                    "CaseId": "123",
                    "CaseNumber": "А40-123456/2024",
                    "CaseType": "G",
                }
            ],
        }
    }

    client = KadArbitrClient()
    await client._ensure_client()

    mock_request = mocker.patch.object(
        client,
        "_request_with_retry",
        return_value=mocker.Mock(
            spec=Response,
            json=lambda: mock_response,
        ),
    )

    result = await client.search_cases(case_number="А40-123456/2024")

    assert result == mock_response
    assert result["Result"]["TotalCount"] == 1
    mock_request.assert_called_once()

    await client.close()


@pytest.mark.asyncio
async def test_search_cases_with_participant(mocker: MockerFixture) -> None:
    """Test case search with participant name."""
    mock_response = {"Result": {"TotalCount": 0, "Items": []}}

    client = KadArbitrClient()
    await client._ensure_client()

    mock_request = mocker.patch.object(
        client,
        "_request_with_retry",
        return_value=mocker.Mock(spec=Response, json=lambda: mock_response),
    )

    result = await client.search_cases(participant_name="ООО Тест")

    assert result["Result"]["TotalCount"] == 0

    # Check that payload includes Sides
    call_args = mock_request.call_args
    payload = call_args.kwargs["json"]
    assert "Sides" in payload
    assert payload["Sides"][0]["Name"] == "ООО Тест"

    await client.close()


@pytest.mark.asyncio
async def test_get_case_card(mocker: MockerFixture) -> None:
    """Test fetching case card HTML."""
    mock_html = "<html><body>Test Case Card</body></html>"

    client = KadArbitrClient()
    await client._ensure_client()

    mock_request = mocker.patch.object(
        client,
        "_request_with_retry",
        return_value=mocker.Mock(spec=Response, text=mock_html),
    )

    result = await client.get_case_card("test-case-id")

    assert result == mock_html
    mock_request.assert_called_once_with("GET", "/Card/test-case-id")

    await client.close()


@pytest.mark.asyncio
async def test_download_document(mocker: MockerFixture) -> None:
    """Test downloading document."""
    mock_content = b"PDF content here"

    client = KadArbitrClient()
    await client._ensure_client()

    mock_request = mocker.patch.object(
        client,
        "_request_with_retry",
        return_value=mocker.Mock(spec=Response, content=mock_content),
    )

    result = await client.download_document("/doc/12345")

    assert result == mock_content
    mock_request.assert_called_once_with("GET", "/doc/12345")

    await client.close()


@pytest.mark.asyncio
async def test_request_with_retry_failure(mocker: MockerFixture) -> None:
    """Test request retry on failure."""
    import httpx

    client = KadArbitrClient(max_retries=2)
    await client._ensure_client()

    # Mock httpx client to raise error
    mocker.patch.object(
        client._client,  # type: ignore
        "request",
        side_effect=httpx.RequestError("Connection failed"),
    )

    with pytest.raises(ConnectionException) as exc_info:
        await client._request_with_retry("GET", "/test")

    assert "Failed after 2 attempts" in str(exc_info.value)

    await client.close()


@pytest.mark.asyncio
async def test_search_cases_error_handling(mocker: MockerFixture) -> None:
    """Test error handling in search."""
    client = KadArbitrClient()
    await client._ensure_client()

    mocker.patch.object(
        client,
        "_request_with_retry",
        side_effect=Exception("Network error"),
    )

    with pytest.raises(ScraperException) as exc_info:
        await client.search_cases(case_number="А40-123456/2024")

    assert "Search failed" in str(exc_info.value)

    await client.close()
