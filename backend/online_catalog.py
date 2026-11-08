"""Explicit public GitHub catalog browsing, pinned downloads and reviewed installs."""
import asyncio
import hashlib
import io
import json
import re
import time
from urllib.parse import quote, urlsplit
from pathlib import PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import httpx
from .import_packages import read_package, skill_document, safe_path, MAX_EXPANDED, MAX_UPLOAD

SOURCES=[
    {'name':'OpenAI · Codex','url':'https://github.com/openai/skills/tree/main/skills/.curated'},
    {'name':'Anthropic · Agent Skills','url':'https://github.com/anthropics/skills/tree/main/skills'},
    {'name':'Claude · Plugins oficiais','url':'https://github.com/anthropics/claude-plugins-official/tree/main/plugins'},
    {'name':'Vercel · Agent Skills','url':'https://github.com/vercel-labs/agent-skills/tree/main/skills'},
]


def source_parts(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='github.com' or parsed.query or parsed.fragment:
        raise ValueError('Use uma URL pública https://github.com/autor/repositorio ou /tree/branch/pasta.')
    parts=parsed.path.strip('/').split('/')
    if len(parts)<2 or not all(re.fullmatch(r'[A-Za-z0-9_.-]+',p) for p in parts[:2]):raise ValueError('Repositório GitHub inválido.')
    repo='/'.join(parts[:2]);ref='HEAD';folder=''
    if len(parts)>2:
        if len(parts)<4 or parts[2]!='tree' or not re.fullmatch(r'[A-Za-z0-9_.-]+',parts[3]):raise ValueError('Use /tree/branch/pasta; nomes de branch com barras não são suportados.')
        ref=parts[3];folder='/'.join(parts[4:])
        if folder:safe_path(folder)
    return repo,ref,folder


class OnlineCatalog:
    def __init__(self):
        self.cache={};self.previews={};self.lock=asyncio.Lock()

    async def fetch(self,client,url,limit):
        # Hosts and paths are constructed exclusively from validated GitHub identifiers.
        async with client.stream('GET',url) as response:
            if response.status_code==403 or response.status_code==429:raise ValueError('Limite público do GitHub atingido. Tente novamente mais tarde.')
            if response.status_code!=200:raise ValueError('Não foi possível consultar o GitHub (HTTP '+str(response.status_code)+').')
            data=bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data)>limit:raise ValueError('Arquivo online excede o limite permitido.')
            return bytes(data)

    async def browse(self,url):
        repo,ref,folder=source_parts(url)
        async with self.lock:
            cached=self.cache.get(url)
            if cached and cached['expires']>time.monotonic():return cached['public']
            async with httpx.AsyncClient(timeout=20,follow_redirects=False,headers={'User-Agent':'Central-IA-Studio/0.5'}) as client:
                commit=json.loads(await self.fetch(client,'https://api.github.com/repos/'+repo+'/commits/'+quote(ref,safe=''),1024*1024))
                sha=commit['sha'];tree_sha=commit['commit']['tree']['sha']
                if not re.fullmatch('[a-f0-9]{40}',sha) or not re.fullmatch('[a-f0-9]{40}',tree_sha):raise ValueError('Commit GitHub inválido.')
                tree=json.loads(await self.fetch(client,'https://api.github.com/repos/'+repo+'/git/trees/'+tree_sha+'?recursive=1',8*1024*1024))
                if tree.get('truncated'):raise ValueError('Repositório muito grande. Importe um pacote ZIP selecionado.')
                files=[f for f in tree['tree'] if f.get('type')=='blob' and f.get('mode') in ('100644','100755') and (not folder or f['path'].startswith(folder+'/'))]
                manifests=[f for f in files if PurePosixPath(f['path']).name=='plugin.json']
                roots={}
                for file in manifests:
                    parent=PurePosixPath(file['path']).parent
                    if parent.name in ('.codex-plugin','.claude-plugin'):parent=parent.parent
                    roots['' if str(parent)=='.' else str(parent)]=file
                candidates=[]
                for root,manifest in roots.items():
                    if any((not root or f['path'].startswith(root+'/')) and (f['path'].endswith('/SKILL.md') or f['path'].endswith('/.mcp.json') or f['path'].endswith('/mcp.json')) for f in files):candidates.append((root,manifest,'plugin'))
                for f in files:
                    if (f['path']=='SKILL.md' or f['path'].endswith('/SKILL.md')) and not any(not root or f['path'].startswith(root+'/') for root in roots):
                        candidates.append((f['path'].rsplit('/',1)[0] if '/' in f['path'] else '',f,'skill'))
                candidates=candidates[:100];semaphore=asyncio.Semaphore(6)
                async def metadata(candidate):
                    root,file,kind=candidate
                    try:
                        async with semaphore:raw=await self.fetch(client,'https://raw.githubusercontent.com/'+repo+'/'+sha+'/'+quote(file['path'],safe='/'),128*1024)
                        meta=skill_document(raw) if kind=='skill' else json.loads(raw)
                        if not isinstance(meta,dict) or not isinstance(meta.get('name'),str) or not isinstance(meta.get('description',''),str):raise ValueError('Metadados inválidos.')
                        key=hashlib.sha256((repo+'\n'+root).encode()).hexdigest()[:24]
                        return {'id':key,'name':meta['name'][:100],'description':meta.get('description','')[:1200],'kind':kind,'root':root,'url':'https://github.com/'+repo+'/tree/'+sha+('/'+quote(root,safe='/') if root else ''),'commit':sha,'repository':repo}
                    except (ValueError,UnicodeError):return None
                results=await asyncio.gather(*(metadata(c) for c in candidates))
            public={'items':[i for i in results if i],'source':url,'commit':sha,'omitted':len(candidates)-sum(i is not None for i in results)}
            if len(self.cache)>=8:self.cache.pop(next(iter(self.cache)))
            self.cache[url]={'expires':time.monotonic()+1200,'public':public,'files':files}
            return public

    async def preview(self,url,key):
        public=await self.browse(url)
        cached=self.cache[url]
        item=next((i for i in public['items'] if i['id']==key),None)
        if not item:raise ValueError('Item não encontrado; consulte o catálogo novamente.')
        root=item['root'];files=[f for f in cached['files'] if not root or f['path'].startswith(root+'/')]
        if not files or len(files)>200 or sum(f.get('size',0) for f in files)>MAX_EXPANDED:raise ValueError('Pacote excede o limite de 200 arquivos / 20 MiB. Importe uma seleção manual.')
        output=io.BytesIO();total=0
        async with httpx.AsyncClient(timeout=20,follow_redirects=False,headers={'User-Agent':'Central-IA-Studio/0.5'}) as client:
            with ZipFile(output,'w',compression=ZIP_DEFLATED) as archive:
                for file in files:
                    path=safe_path(file['path'][len(root)+1:] if root else file['path'])
                    data=await self.fetch(client,'https://raw.githubusercontent.com/'+item['repository']+'/'+item['commit']+'/'+quote(file['path'],safe='/'),2*1024*1024)
                    total+=len(data)
                    if total>MAX_EXPANDED:raise ValueError('Pacote expandido excede 20 MiB.')
                    entry=ZipInfo(path);entry.compress_type=ZIP_DEFLATED
                    entry.external_attr=(0o100700 if file['mode']=='100755' else 0o100600)<<16
                    archive.writestr(entry,data)
        data=output.getvalue()
        if len(data)>MAX_UPLOAD:raise ValueError('Pacote comprimido excede 8 MiB.')
        package=read_package(data,'online.zip');package['source']=item['url']
        ticket=hashlib.sha256(data+str(time.monotonic()).encode()).hexdigest()
        self.previews={k:v for k,v in self.previews.items() if v['expires']>time.monotonic()}
        if len(self.previews)>=4:self.previews.pop(next(iter(self.previews)))
        self.previews[ticket]={'package':package,'expires':time.monotonic()+600,'entry':item}
        return ticket,package,item

    def reviewed(self,ticket,digest):
        preview=self.previews.get(ticket)
        if not preview or preview['expires']<time.monotonic() or preview['package']['digest']!=digest:raise ValueError('Prévia expirada ou alterada. Revise o pacote novamente.')
        return preview
