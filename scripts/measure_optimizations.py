"""Controlled subsystem comparisons; not an end-to-end benchmark of user GGUFs."""
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))


def main():
    from backend.engine import Engine
    from backend.storage import Store
    from backend.gguf import metadata,_cached_metadata
    report={}
    for eager in (False,True):
        code="import time,psutil,json,sys; start=time.perf_counter(); import backend.attachments; "
        if eager:code+='import PIL.Image,pypdf; '
        code+="p=psutil.Process(); print(json.dumps({'seconds':time.perf_counter()-start,'rss':p.memory_info().rss,'pypdf_loaded':'pypdf' in sys.modules,'pillow_loaded':'PIL.Image' in sys.modules}))"
        samples=[json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True)) for _ in range(3)]
        report['eager_parsers' if eager else 'lazy_parsers']={'samples':samples,'median_rss':statistics.median(s['rss'] for s in samples),'median_seconds':statistics.median(s['seconds'] for s in samples)}
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def do_GET(self):
            data={'/api/extra/version':{'result':'KoboldCpp','version':'fixture'},'/api/v1/model':{'result':'fixture'},'/api/extra/true_max_context_length':{'value':4096}}
            body=json.dumps(data.get(self.path,{})).encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory);store.put('settings',{'engine_url':f'http://127.0.0.1:{server.server_port}'})
            async def measure():
                for pooled in (False,True):
                    engine=Engine(store)
                    if pooled:await engine.open_http_pool()
                    samples=[]
                    for _ in range(10):
                        start=time.perf_counter();assert (await engine.status())['connected'];samples.append(time.perf_counter()-start)
                    await engine.close_http_pool()
                    report['http_pooled' if pooled else 'http_unpooled']={'samples_seconds':samples,'median_seconds':statistics.median(samples)}
            asyncio.run(measure())
            import struct
            folder=Path(directory)/'headers';folder.mkdir();files=[]
            def string(s):b=s.encode();return struct.pack('<Q',len(b))+b
            for i in range(17):
                file=folder/f'header-{i}.gguf'
                entries={'general.name':'Fixture','general.architecture':'qwen2','general.file_type':15}
                data=b'GGUF'+struct.pack('<IQQ',3,0,len(entries))
                for key,value in entries.items():data+=string(key)+struct.pack('<I',4 if isinstance(value,int) else 8)+(struct.pack('<I',value) if isinstance(value,int) else string(value))
                file.write_bytes(data);files.append(file)
            for cached in (False,True):
                _cached_metadata.cache_clear();samples=[]
                for _ in range(10):
                    start=time.perf_counter()
                    for file in files:
                        if not cached:_cached_metadata.cache_clear()
                        metadata(file)
                    samples.append(time.perf_counter()-start)
                report['gguf_cached' if cached else 'gguf_uncached']={'samples_seconds':samples,'median_seconds':statistics.median(samples),'fixtures':'17 synthetic headers, no inference/real model compatibility claim'}
    finally:server.shutdown();server.server_close();thread.join()
    (ROOT/'work/optimization-measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
