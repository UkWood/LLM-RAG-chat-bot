"""The real HTTP adapter talks to a local OpenAI-compatible server, no cloud key."""
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from saturn_ai.rag.provider import OpenAICompatibleClient,ProviderSettings,ProviderError

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.received.append((self.path,self.headers.get('Authorization'),payload))
        if self.server.delay:time.sleep(self.server.delay)
        status=self.server.status
        if self.path!='/v1/chat/completions' or payload.get('model')!='ready-model':status=400
        self.send_response(status)
        if status==302:self.send_header('Location','http://127.0.0.1:1/stolen')
        self.end_headers()
        try:self.wfile.write(self.server.body)
        except (BrokenPipeError,ConnectionResetError):pass

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads=True;self.server.received=[];self.server.status=200;self.server.delay=0
        self.server.body=json.dumps({'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'{"ok":true}'}}]}).encode()
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.base='http://127.0.0.1:%d/v1'%self.server.server_port
    def client(self,**kw):
        return OpenAICompatibleClient(ProviderSettings(self.base,'ready-model','test-key',allow_local_http=True,**kw))
    def test_configured_api_model_and_key_reach_only_expected_endpoint(self):
        client=self.client();self.assertEqual(client.complete('JSON only','public synthetic prompt'),{'ok':True})
        path,auth,data=self.server.received[0]
        self.assertEqual(path,'/v1/chat/completions');self.assertEqual(auth,'Bearer test-key')
        self.assertEqual(data['model'],'ready-model');self.assertEqual(data['messages'][1]['content'],'public synthetic prompt')
        self.assertNotIn('test-key',repr(client.settings));self.assertNotIn('test-key',json.dumps(client.identity))
    def test_redirect_and_http_failures_are_errors_without_response_or_key_leak(self):
        for status in (302,401,429,500):
            self.server.status=status;self.server.body=b'test-key should not be exposed'
            with self.subTest(status=status),self.assertRaises(ProviderError) as ctx:self.client().complete('s','u')
            self.assertNotIn('test-key',str(ctx.exception))
    def test_model_json_duplicates_truncation_and_tool_calls_are_rejected(self):
        for content,finish,tools in [('{"x":1,"x":2}','stop',None),('{','stop',None),('{"x":1}','length',None),('{"x":1}','tool_calls',[{}])]:
            self.server.body=json.dumps({'choices':[{'finish_reason':finish,'message':{'content':content,'tool_calls':tools}}]}).encode()
            with self.subTest(content=content,finish=finish),self.assertRaises(ProviderError):self.client().complete('s','u')
    def test_timeout_stays_error(self):
        self.server.delay=.15
        with self.assertRaises(ProviderError):self.client(timeout=.03).complete('s','u')
    def test_remote_config_requires_https_and_credential(self):
        for base,key in [('http://example.com/v1','k'),('https://user:pw@example.com/v1','k'),('https://example.com/v1?token=x','k'),('https://example.com/v1','')]:
            with self.subTest(base=base),self.assertRaises(ValueError):ProviderSettings(base,'model',key)

    def test_cli_smoke_checks_real_compatible_http_shape_without_exposing_key(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from saturn_ai.rag.__main__ import main
        self.server.body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"ready":true}'}}]}).encode()
        env={'LLM_BASE_URL':self.base,'LLM_MODEL':'ready-model','LLM_API_KEY':'test-key','LLM_ALLOW_LOCAL_HTTP':'1',
            'LLM_TIMEOUT_SECONDS':'1','LLM_MAX_TOKENS':'128','LLM_JSON_MODE':'1'}
        output=StringIO()
        with patch.dict('os.environ',env),redirect_stdout(output):status=main(['smoke'])
        self.assertEqual(status,0);self.assertEqual(json.loads(output.getvalue())['status'],'compatible')
        self.assertNotIn('test-key',output.getvalue())
