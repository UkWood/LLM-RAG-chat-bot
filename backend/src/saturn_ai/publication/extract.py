"""Canonical HTML text and isolated PDF extraction, never taxonomy parsing."""
from dataclasses import dataclass,field
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urljoin
from .policy import checked_url


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.all=[];self.main=[];self.links=[];self.title=[];self.stack=[];self.ignored=0;self.in_main=0;self.in_title=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a' and attrs.get('href'):self.links.append(attrs['href'])
        if tag in ('script','style','noscript','nav','header','footer','svg'):
            self.ignored+=1;self.stack.append(tag)
        if tag in ('main','article'):self.in_main+=1
        if tag=='title':self.in_title+=1
        if tag in ('p','div','section','tr','h1','h2','h3','h4','br','li'):self.add('\n')
        if tag in ('td','th'):self.add(' | ')
    def handle_endtag(self,tag):
        if tag in ('p','div','section','tr','h1','h2','h3','h4','li'):self.add('\n')
        if self.stack and tag==self.stack[-1]:self.stack.pop();self.ignored-=1
        if tag in ('main','article'):self.in_main=max(0,self.in_main-1)
        if tag=='title':self.in_title=max(0,self.in_title-1)
    def add(self,text):
        if not self.ignored and not self.in_title:
            self.all.append(text)
            if self.in_main:self.main.append(text)
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        self.add(data)


def extract_pdf(raw):
    if not raw.startswith(b'%PDF-') or len(raw)>20_000_000:raise ValueError('Invalid PDF')
    bwrap=shutil.which('bwrap')
    if not bwrap:raise ValueError('PDF isolation unavailable; quarantine')
    worker=Path(__file__).with_name('pdf_worker.py').resolve()
    command=[bwrap,'--unshare-all','--die-with-parent','--new-session','--clearenv']
    for directory in dict.fromkeys(('/usr','/lib','/lib64',sys.base_prefix,sys.prefix)):
        if Path(directory).exists():command+=['--ro-bind',directory,directory]
    command+=['--ro-bind',str(worker),str(worker),'--proc','/proc','--dev','/dev','--tmpfs','/tmp',
              '--setenv','PYTHONIOENCODING','utf-8',sys.executable,'-I',str(worker)]
    try:
        run=subprocess.run(command,input=raw,capture_output=True,timeout=20,check=False,env={'PATH':os.defpath})
        if run.returncode or len(run.stdout)>2_000_000:raise ValueError('PDF isolation/extraction failed; quarantine')
        pages=json.loads(run.stdout)
        if (not isinstance(pages,list) or not 1<=len(pages)<=200 or any(
            not isinstance(p,list) or len(p)!=2 or p[0]!=i or type(p[1]) is not str or not p[1].strip()
            for i,p in enumerate(pages,1))):raise ValueError('Invalid PDF extraction')
        return tuple((number,text) for number,text in pages)
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
        raise ValueError('PDF extraction unavailable; quarantine') from exc


@dataclass(frozen=True)
class PublishedSource:
    url: str
    content: bytes
    media_type: str
    title: str=field(init=False)
    pages: tuple=field(init=False)
    links: tuple=field(init=False)
    content_hash: str=field(init=False)

    def __post_init__(self):
        if self.url!=checked_url(self.url) or type(self.content) is not bytes:raise ValueError('Invalid source receipt')
        if self.media_type=='text/html':
            if len(self.content)>2_000_000:raise ValueError('HTML over limit')
            parser=PageParser();parser.feed(self.content.decode('utf-8-sig'))
            raw=''.join(parser.main or parser.all)
            text='\n'.join(re.sub(r'[ \t\r\f\v]+',' ',line).strip(' |') for line in raw.splitlines())
            text=re.sub(r'\n{3,}','\n\n',text).strip()
            pages=((None,text),) if text else ()
            links=[]
            for href in parser.links:
                try:links.append(checked_url(urljoin(self.url,href)))
                except ValueError:continue
            title=' '.join(''.join(parser.title).split()) or self.url
        elif self.media_type=='application/pdf':
            pages=extract_pdf(self.content);links=[];title=self.url.rsplit('/',1)[-1]
        else:raise ValueError('Unsupported source type')
        object.__setattr__(self,'pages',pages);object.__setattr__(self,'links',tuple(dict.fromkeys(links)))
        object.__setattr__(self,'title',title[:300]);object.__setattr__(self,'content_hash',sha256(self.content).hexdigest())
