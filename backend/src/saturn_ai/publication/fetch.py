"""Bounded anonymous HTTPS reads; only configured publication destinations."""
from dataclasses import dataclass
import ipaddress
import socket
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler,Request,build_opener
from urllib.parse import urljoin,urlsplit
from .policy import checked_url

@dataclass(frozen=True)
class Fetched:
    url: str
    content: bytes
    media_type: str
    status: int=200

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class PublicationFetcher:
    def __init__(self,policy,*,timeout=15,resolver=socket.getaddrinfo):
        self.policy=policy;self.timeout=timeout;self.resolver=resolver;self.opener=build_opener(NoRedirect())
    def __call__(self,url,kind):
        allowed=self.policy.allows_pdf if kind=='pdf' else self.policy.allows_page
        for _ in range(4):
            url=checked_url(url)
            if not allowed(url):raise ValueError('Source outside configured scope')
            addresses=self.resolver(urlsplit(url).hostname,443,type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ValueError('Nonpublic resolved destination')
            request=Request(url,headers={'User-Agent':'SaturnConsultant-Indexer/1','Accept-Encoding':'identity'})
            try:response=self.opener.open(request,timeout=self.timeout)
            except HTTPError as exc:
                if exc.code in (301,302,303,307,308):
                    location=exc.headers.get('Location');exc.close()
                    if not location:raise ValueError('Missing redirect location')
                    url=urljoin(url,location);continue
                if exc.code in (404,410):
                    exc.close();return Fetched(url,b'','',exc.code)
                exc.close();raise ValueError('Source HTTP failure') from None
            with response:
                if response.status!=200:raise ValueError('Unexpected source status')
                limit=20_000_000 if kind=='pdf' else 2_000_000
                raw=response.read(limit+1)
                if len(raw)>limit:raise ValueError('Source size limit')
                media=response.headers.get_content_type()
                if kind=='pdf' and media=='application/octet-stream' and raw.startswith(b'%PDF-'):media='application/pdf'
                if media!=('application/pdf' if kind=='pdf' else 'text/html'):raise ValueError('Unsupported source content type')
                return Fetched(url,raw,media)
        raise ValueError('Redirect limit')
