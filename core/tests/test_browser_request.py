"""Target requests use the same Chrome impersonation as public web fetch."""
import pytest

from app.services import web_research
from app.services.pentest_workers import Action


@pytest.mark.asyncio
async def test_browser_exchange_impersonates_chrome_and_stays_in_scope(monkeypatch):
    assert Action.model_validate({'action': 'browser_request', 'url': 'https://target.test/api/register', 'query': 'POST'}).action == 'browser_request'
    captured = {}

    class Response:
        status_code = 400
        content = b'{"detail":"Disposable email addresses are not allowed"}'
        headers = {'content-type': 'application/json'}

    class Session:
        def __init__(self, impersonate='chrome', curl_options=None):
            captured['impersonate'] = impersonate
            captured['resolve'] = curl_options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, **kwargs):
            captured['method'] = method
            captured['redirects'] = kwargs.get('allow_redirects')
            captured['headers'] = kwargs.get('headers')
            captured['data'] = kwargs.get('data')
            return Response()

    import curl_cffi.requests as requests
    monkeypatch.setattr(requests, 'AsyncSession', Session)

    async def addresses(host):
        assert host == 'target.test'
        return ['203.0.113.10']

    monkeypatch.setattr(web_research, 'public_addresses', addresses)
    result = await web_research.browser_exchange(
        'POST', 'https://target.test/api/register', '{"email":"a@b.c"}', 'application/json', '',
        ['target.test'], [])
    assert captured['impersonate'] == 'chrome'
    assert captured['redirects'] is False
    assert captured['headers']['Content-Type'] == 'application/json'
    assert result['status'] == 400 and 'Disposable' in result['body']
    with pytest.raises(ValueError):
        await web_research.browser_exchange('GET', 'https://other.test/', '', '', '', ['target.test'], [])
