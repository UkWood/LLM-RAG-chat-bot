"""Explicit publication scope. New bytes inherit policy, not fabricated manual approvals."""
from dataclasses import dataclass
from hashlib import sha256
import ipaddress
import json
from urllib.parse import urlsplit, urlunsplit, unquote


def checked_url(value):
    if not isinstance(value,str) or len(value)>2048 or any(ord(c)<33 for c in value):
        raise ValueError('Invalid publication URL')
    u=urlsplit(value)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):
        raise ValueError('Public HTTPS source required')
    host=u.hostname.lower()
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')):
        raise ValueError('Private source denied')
    try:
        if not ipaddress.ip_address(host).is_global:raise ValueError('Nonpublic source denied')
    except ValueError as exc:
        if 'does not appear' not in str(exc):raise
    path=unquote(u.path or '/')
    if '\\' in path or '%' in path or any(p in ('.','..') for p in path.split('/')):
        raise ValueError('Ambiguous publication path')
    return urlunsplit(('https',u.netloc.lower(),u.path or '/',u.query,''))


@dataclass(frozen=True)
class PublicationPolicy:
    site_root: str
    pdf_origins: tuple[str,...]=()
    cloud_allowed: bool=False
    max_pages: int=200
    max_pdfs: int=100
    max_age_seconds: int=172800
    refresh_timezone: str="UTC"

    def __post_init__(self):
        root=checked_url(self.site_root)
        u=urlsplit(root)
        if not u.path.endswith('/') or u.query or root!=self.site_root:
            raise ValueError('Canonical root with trailing slash required')
        if (type(self.cloud_allowed) is not bool or type(self.max_pages) is not int or not 1<=self.max_pages<=1000
                or type(self.max_pdfs) is not int or not 0<=self.max_pdfs<=500
                or type(self.max_age_seconds) is not int or not 86400<=self.max_age_seconds<=604800):
            raise ValueError('Invalid publication bounds')
        from zoneinfo import ZoneInfo
        try:ZoneInfo(self.refresh_timezone)
        except (ValueError,TypeError,KeyError):raise ValueError('Invalid refresh timezone') from None
        for origin in self.pdf_origins:
            if checked_url(origin+'/').rstrip('/')!=origin or urlsplit(origin).path:
                raise ValueError('Canonical PDF origin required')

    @property
    def revision(self):
        from dataclasses import asdict
        return sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()

    def allows_page(self,url):
        try:
            u=urlsplit(checked_url(url));r=urlsplit(self.site_root)
            return u.netloc==r.netloc and unquote(u.path).startswith(unquote(r.path)) and not u.path.lower().endswith('.pdf')
        except ValueError:return False

    def allows_pdf(self,url):
        try:
            u=urlsplit(checked_url(url));origin='https://'+u.netloc
            return (origin in self.pdf_origins or self.allows_page_origin(url)) and unquote(u.path).lower().endswith('.pdf')
        except ValueError:return False

    def allows_page_origin(self,url):
        u=urlsplit(url);r=urlsplit(self.site_root)
        return u.netloc==r.netloc and unquote(u.path).startswith(unquote(r.path))
