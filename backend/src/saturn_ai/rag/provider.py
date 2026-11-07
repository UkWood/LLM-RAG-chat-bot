"""Small configurable OpenAI-compatible JSON client, independent of retrieval."""
from dataclasses import dataclass,field
import ipaddress
import json
import os
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
from urllib.request import Request,build_opener
from ..ingestion.registry import unique_object
from ..publication.fetch import NoRedirect

class ProviderError(RuntimeError):pass

def loopback(host):
    if host=='localhost':return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False

@dataclass(frozen=True)
class ProviderSettings:
    base_url: str
    model: str
    api_key: str=field(repr=False)
    timeout: float=60.
    max_tokens: int=2048
    json_mode: bool=True
    allow_local_http: bool=False

    def __post_init__(self):
        u=urlsplit(self.base_url)
        if (not u.hostname or u.username or u.password or u.query or u.fragment
                or u.scheme not in ('https','http') or self.base_url!=self.base_url.rstrip('/')
                or u.scheme=='http' and not (self.allow_local_http and loopback(u.hostname))):
            raise ValueError('Invalid model endpoint')
        if (not isinstance(self.model,str) or not 1<=len(self.model)<=200 or any(c.isspace() for c in self.model)
                or not isinstance(self.api_key,str) or any(c.isspace() for c in self.api_key)
                or not loopback(u.hostname) and not self.api_key
                or type(self.max_tokens) is not int or not 16<=self.max_tokens<=8192
                or type(self.timeout) not in (int,float) or not .01<=self.timeout<=180
                or type(self.json_mode) is not bool):raise ValueError('Invalid model configuration')
    @property
    def remote(self):return not loopback(urlsplit(self.base_url).hostname)
    @classmethod
    def from_env(cls):
        try:
            return cls(os.environ['LLM_BASE_URL'].rstrip('/'),os.environ['LLM_MODEL'],os.environ.get('LLM_API_KEY',''),
                timeout=float(os.environ.get('LLM_TIMEOUT_SECONDS','60')),max_tokens=int(os.environ.get('LLM_MAX_TOKENS','2048')),
                json_mode=os.environ.get('LLM_JSON_MODE','1')=='1',allow_local_http=os.environ.get('LLM_ALLOW_LOCAL_HTTP','0')=='1')
        except (KeyError,ValueError):raise ValueError('LLM_BASE_URL/LLM_MODEL/LLM_API_KEY configuration required') from None


def strict_json(value):
    def reject_constant(value):raise ValueError('Nonfinite JSON value')
    return json.loads(value,object_pairs_hook=unique_object,parse_constant=reject_constant)

class OpenAICompatibleClient:
    def __init__(self,settings):
        self.settings=settings;self.opener=build_opener(NoRedirect())
    @property
    def identity(self):
        return dict(kind='openai-compatible',base_url=self.settings.base_url,model=self.settings.model,
            max_tokens=self.settings.max_tokens,json_mode=self.settings.json_mode)
    @property
    def remote(self):return self.settings.remote
    def complete(self,system,user):
        if (not isinstance(system,str) or not isinstance(user,str) or len(system)+len(user)>50000):
            raise ProviderError('request_limit')
        payload=dict(model=self.settings.model,messages=[dict(role='system',content=system),dict(role='user',content=user)],
            temperature=0,max_tokens=self.settings.max_tokens)
        if self.settings.json_mode:payload['response_format']={'type':'json_object'}
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if self.settings.api_key:headers['Authorization']='Bearer '+self.settings.api_key
        request=Request(self.settings.base_url+'/chat/completions',data=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode(),headers=headers,method='POST')
        try:
            with self.opener.open(request,timeout=self.settings.timeout) as response:
                raw=response.read(1_000_001)
                if len(raw)>1_000_000:raise ProviderError('response_limit')
            try:
                result=strict_json(raw)
            except (ValueError,UnicodeError):raise ProviderError('invalid_response_envelope') from None
            if not isinstance(result,dict):raise ProviderError('invalid_response_envelope')
            choices=result.get('choices')
            if (not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict)
                    or not isinstance(choices[0].get('message'),dict)):
                raise ProviderError('invalid_response_envelope')
            choice=choices[0];message=choice['message']
            if choice.get('finish_reason')=='length':raise ProviderError('output_truncated')
            if choice.get('finish_reason')!='stop' or message.get('tool_calls'):
                raise ProviderError('unsupported_response_shape')
            text=message.get('content')
            if not isinstance(text,str):raise ProviderError('invalid_response_content')
            try:
                value=strict_json(text)
            except ValueError:raise ProviderError('invalid_response_content') from None
            if not isinstance(value,dict):raise ProviderError('invalid_response_content')
            return value
        except HTTPError as exc:
            code=exc.code;exc.close();raise ProviderError('http_'+str(code)) from None
        except ProviderError:raise
        except TimeoutError:raise ProviderError('timeout') from None
        except URLError as exc:
            raise ProviderError('timeout' if isinstance(exc.reason,TimeoutError) else 'transport_unavailable') from None
        except OSError:raise ProviderError('transport_unavailable') from None
