"""Text-only PDF worker. Invoked inside a filesystem/network namespace."""
import json
import resource
import sys
from io import BytesIO

if __name__=='__main__':
    try:
        resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
        resource.setrlimit(resource.RLIMIT_CPU,(10,10))
        resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
        from pypdf import PdfReader
        raw=sys.stdin.buffer.read(20_000_001)
        if not raw.startswith(b'%PDF-') or len(raw)>20_000_000:raise ValueError()
        reader=PdfReader(BytesIO(raw),strict=True)
        if reader.is_encrypted or not 1<=len(reader.pages)<=200:raise ValueError()
        result=[];total=0
        for number,page in enumerate(reader.pages,1):
            stream=page.get_contents()
            if stream is not None and len(stream.get_data())>10_000_000:raise ValueError()
            text=page.extract_text().strip();total+=len(text)
            if not text or '\x00' in text or len(text)>50000 or total>500000:raise ValueError()
            result.append([number,text])
        print(json.dumps(result,ensure_ascii=False))
    except Exception:sys.exit(2)
