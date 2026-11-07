"""Trusted operator smoke and grounded answer CLI; no public chat endpoint."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from .provider import OpenAICompatibleClient,ProviderSettings,ProviderError


def main(argv=None):
    parser=argparse.ArgumentParser(description='Ordinary grounded RAG operator CLI (implementation in progress)')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('smoke',help='One public synthetic API compatibility request; not a quality benchmark')
    ask=sub.add_parser('ask',help='Answer against a current publication store and checked local models')
    for name in ('policy','store','model-dir','reranker-dir'):ask.add_argument('--'+name,type=Path,required=True)
    ask.add_argument('--query',required=True)
    ask.add_argument('--allow-cloud',action='store_true',help='Operator authorizes this configured remote provider')
    ask.add_argument('--public-question',action='store_true',help='Operator attests question contains only public content')
    args=parser.parse_args(argv)
    try:
        settings=ProviderSettings.from_env()
        if args.command=='ask':
            from .runtime import load_runtime
            from ..publication.policy import PublicationPolicy
            from ..publication.store import PublicationStore
            client=OpenAICompatibleClient(settings)
            if client.remote and not (args.allow_cloud and args.public_question):
                print(json.dumps(dict(status='error',reason_code='cloud_operator_flags_required')));return 2
            try:
                from .provider import strict_json
                data=strict_json(args.policy.read_bytes());data['pdf_origins']=tuple(data.get('pdf_origins',()))
                store=PublicationStore(args.store,PublicationPolicy(**data))
                if client.remote and not store.policy.cloud_allowed:
                    print(json.dumps(dict(status='error',reason_code='cloud_source_not_approved')));return 2
                with load_runtime(store,args.model_dir,args.reranker_dir,client) as runtime:
                    answer=runtime.app.answer(args.query,public_question=args.public_question)
                print(json.dumps(answer.to_dict(),ensure_ascii=False))
                return 2 if answer.status=='error' else 0
            except (ValueError,OSError,LookupError,TypeError,KeyError):
                print(json.dumps(dict(status='error',reason_code='runtime_unavailable')));return 2
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
