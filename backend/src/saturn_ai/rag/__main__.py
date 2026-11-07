"""Provider readiness probe. The full answer/runtime CLI is the next work item."""
import argparse
from dataclasses import replace
import json
from .provider import OpenAICompatibleClient,ProviderSettings,ProviderError


def main(argv=None):
    parser=argparse.ArgumentParser(description='Ordinary grounded RAG operator CLI (implementation in progress)')
    parser.add_subparsers(dest='command',required=True).add_parser('smoke',help='One public synthetic API compatibility request; not a quality benchmark')
    parser.parse_args(argv)
    try:
        settings=ProviderSettings.from_env()
        client=OpenAICompatibleClient(replace(settings,max_tokens=min(settings.max_tokens,512)))
        result=client.complete('Return JSON only. Follow the requested JSON schema.',
            'Public synthetic compatibility test. Return exactly this JSON object: {"ready":true}.')
        if result!={'ready':True}:
            print(json.dumps(dict(status='incompatible',reason_code='unexpected_smoke_object')));return 1
        print(json.dumps(dict(status='compatible',scope='HTTP/JSON contract only',provider=client.identity),ensure_ascii=False));return 0
    except ProviderError as exc:
        print(json.dumps(dict(status='error',reason_code=str(exc))));return 2
    except ValueError:
        print(json.dumps(dict(status='error',reason_code='provider_configuration_required')));return 2

if __name__=='__main__':raise SystemExit(main())
