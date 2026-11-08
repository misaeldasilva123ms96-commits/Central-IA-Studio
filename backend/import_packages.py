"""Portable/legacy plugin and SKILL.md import. Files stay in SQLite until needed."""
import hashlib
import io
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat
import uuid
from zipfile import ZipFile,BadZipFile
import yaml

MAX_UPLOAD=8*1024*1024
MAX_EXPANDED=20*1024*1024

class MetadataLoader(yaml.SafeLoader):
    def compose_node(self,parent,index):
        self.count=getattr(self,'count',0)+1
        if self.count>200 or self.check_event(yaml.AliasEvent):raise ValueError('Metadados YAML complexos ou aliases não são suportados.')
        return super().compose_node(parent,index)


def safe_path(value):
    if not isinstance(value,str) or not value or len(value)>512 or '\\' in value or ':' in value or any(ord(c)<32 for c in value):raise ValueError('Caminho inválido no pacote.')
    p=PurePosixPath(value)
    reserved={'CON','PRN','AUX','NUL'}|{'COM'+str(i) for i in range(1,10)}|{'LPT'+str(i) for i in range(1,10)}
    if any(part.rstrip(' .')!=part or part.split('.')[0].upper() in reserved for part in p.parts):raise ValueError('Nome de arquivo incompatível com Windows.')
    if p.is_absolute() or '..' in p.parts:raise ValueError('O pacote contém caminho fora da pasta de instalação.')
    return str(p)


def skill_document(raw):
    if len(raw)>128*1024:raise ValueError('SKILL.md limitado a 128 KiB.')
    text=raw.decode('utf-8-sig')
    match=re.match(r'\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)\Z',text,re.S)
    if not match or len(match[1])>8192:raise ValueError('SKILL.md precisa de frontmatter YAML com name e description.')
    try:meta=yaml.load(match[1],Loader=MetadataLoader)
    except yaml.YAMLError as e:raise ValueError('Frontmatter YAML inválido.') from e
    if not isinstance(meta,dict):raise ValueError('Metadados da habilidade precisam ser um objeto.')
    name=meta.get('name');description=meta.get('description');body=match[2].strip()
    if not isinstance(name,str) or not 1<=len(name.strip())<=80 or any(ord(c)<32 for c in name):raise ValueError('Nome da habilidade inválido.')
    if not isinstance(description,str) or not 1<=len(description.strip())<=1200:raise ValueError('Descrição da habilidade inválida.')
    if not body or len(body)>48000:raise ValueError('Instruções precisam ter entre 1 e 48.000 caracteres.')
    return {'name':name.strip(),'description':description.strip(),'instructions':body,'implicit':True}


def read_package(data,name):
    if len(data)>MAX_UPLOAD:raise ValueError('Pacote limitado a 8 MiB.')
    files={};modes={}
    if name.lower().endswith('.md'):
        files={'SKILL.md':data};modes={'SKILL.md':0o600}
    elif name.lower().endswith('.zip'):
        try:
            with ZipFile(io.BytesIO(data)) as archive:
                if len(archive.infolist())>200:raise ValueError('Pacote limitado a 200 entradas.')
                total=0
                for entry in archive.infolist():
                    path=safe_path(entry.filename.rstrip('/'))
                    if stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Links simbólicos não são aceitos no pacote.')
                    if entry.is_dir():continue
                    if path=='.':raise ValueError('Nome de arquivo inválido no ZIP.')
                    total+=entry.file_size
                    if total>MAX_EXPANDED or entry.file_size>2*1024*1024:raise ValueError('Conteúdo expandido excede o limite do pacote.')
                    if path.casefold() in {p.casefold() for p in files}:raise ValueError('Arquivo duplicado ou ambíguo no pacote.')
                    files[path]=archive.read(entry);modes[path]=0o700 if (entry.external_attr>>16)&0o111 else 0o600
        except (BadZipFile,RuntimeError) as e:raise ValueError('ZIP inválido ou criptografado.') from e
    else:raise ValueError('Envie SKILL.md ou um pacote ZIP.')
    if not files:raise ValueError('Pacote vazio.')
    # GitHub ZIPs commonly include a single enclosing directory.
    while all('/' in p for p in files) and len({p.split('/')[0] for p in files})==1:
        files={p.split('/',1)[1]:v for p,v in files.items()};modes={p.split('/',1)[1]:v for p,v in modes.items()}
    manifest_path=next((p for p in ['plugin.json','.codex-plugin/plugin.json','.claude-plugin/plugin.json'] if p in files),None)
    warnings=[];skills=[];servers={};manifest={}
    if manifest_path:
        try:manifest=json.loads(files[manifest_path])
        except (ValueError,RecursionError) as e:raise ValueError('Manifesto do plugin inválido.') from e
        if not isinstance(manifest,dict):raise ValueError('Manifesto precisa ser um objeto.')
        plugin_name=manifest.get('name');description=manifest.get('description','Plugin importado')
        if not isinstance(plugin_name,str) or not 1<=len(plugin_name)<=100 or not isinstance(description,str) or len(description)>1200:raise ValueError('Nome/descrição do plugin inválidos.')
        skill_paths=[p for p in files if p.startswith('skills/') and p.endswith('/SKILL.md')]
        declared=manifest.get('skills',[])
        if isinstance(declared,str):declared=[declared]
        if not isinstance(declared,list):raise ValueError('Campo skills inválido.')
        for directory in declared:
            if not isinstance(directory,str):raise ValueError('Caminho de habilidade inválido.')
            directory=safe_path(directory.removeprefix('./').rstrip('/'))
            skill_paths += [p for p in files if (p==directory or p.startswith(directory+'/')) and p.endswith('SKILL.md')]
        for path in dict.fromkeys(skill_paths):skills.append(skill_document(files[path])|{'root':str(PurePosixPath(path).parent)})
        for path in ['mcp.json','.mcp.json']:
            if path in files:
                try:doc=json.loads(files[path])
                except (ValueError,RecursionError) as e:raise ValueError('Configuração MCP inválida.') from e
                if not isinstance(doc,dict) or not isinstance(doc.get('mcpServers',{}),dict):raise ValueError('mcpServers precisa ser um objeto.')
                servers.update(doc.get('mcpServers',{}))
        inline=manifest.get('mcpServers')
        if isinstance(inline,dict):servers.update(inline)
        elif isinstance(inline,str):
            path=safe_path(inline.removeprefix('./'))
            if path not in files:raise ValueError('Arquivo MCP declarado não encontrado.')
            try:doc=json.loads(files[path])
            except (ValueError,RecursionError) as e:raise ValueError('Arquivo MCP inválido.') from e
            if not isinstance(doc,dict):raise ValueError('Arquivo MCP precisa ser um objeto.')
            servers.update(doc.get('mcpServers',doc))
        if 'hooks' in manifest or any(p.startswith('hooks/') for p in files):warnings.append('Hooks não são executados por esta versão.')
        if 'apps' in manifest or '.app.json' in files:warnings.append('Conexões exclusivas da conta ChatGPT não são importadas. Configure o serviço por MCP.')
        kind='plugin'
    elif 'SKILL.md' in files:
        skill=skill_document(files['SKILL.md']);plugin_name=skill['name'];description=skill['description'];skills=[skill|{'root':'.'}];kind='skill'
    else:raise ValueError('Não foi encontrado plugin.json, .codex-plugin/plugin.json, .claude-plugin/plugin.json ou SKILL.md na raiz.')
    if len(skills)>20 or len(servers)>8:raise ValueError('Pacote limitado a 20 habilidades e 8 servidores MCP.')
    if not skills and not servers:raise ValueError('Pacote sem habilidades ou servidores MCP compatíveis.')
    for skill in skills:
        config_path=str(PurePosixPath(skill['root'])/'agents/openai.yaml')
        if config_path in files:
            if len(files[config_path])>8192:raise ValueError('agents/openai.yaml excede 8 KiB.')
            try:settings=yaml.load(files[config_path].decode('utf-8'),Loader=MetadataLoader)
            except yaml.YAMLError as e:raise ValueError('agents/openai.yaml inválido.') from e
            if isinstance(settings,dict) and isinstance(settings.get('policy'),dict):
                implicit=settings['policy'].get('allow_implicit_invocation',True)
                if not isinstance(implicit,bool):raise ValueError('allow_implicit_invocation precisa ser booleano.')
                skill['implicit']=implicit
            if isinstance(settings,dict) and isinstance(settings.get('dependencies'),dict):
                dependencies=settings['dependencies'].get('tools',[])
                if isinstance(dependencies,list):
                    for dependency in dependencies[:16]:
                        if not isinstance(dependency,dict) or dependency.get('type')!='mcp':continue
                        label=str(dependency.get('value','dependency'))[:100]
                        if dependency.get('url'):
                            servers.setdefault(label,{'transport':dependency.get('transport','streamable_http'),'url':dependency['url']})
                        else:warnings.append('Dependência MCP '+label+' requer configuração própria em Conexões MCP.')
    if len(servers)>8:raise ValueError('Pacote limitado a 8 servidores MCP.')
    if any(not skill['implicit'] for skill in skills):warnings.append('O pacote recomenda uso manual. No Central IA, o controle de uso automático definido por você prevalece.')
    # Parse and validate connections before storing anything. No connection is started here.
    from .mcp_bridge import validate_config
    connections=[]
    for server_name,config in servers.items():
        cfg=validate_config(config,imported=True)
        connections.append({'name':str(server_name)[:100],'config':cfg})
        if config.get('auth') or config.get('oauth') or (isinstance(config.get('extensions'),dict) and isinstance(config['extensions'].get('com.openai'),dict) and config['extensions']['com.openai'].get('auth')):warnings.append('OAuth não é transferido da conta Codex. Configure credenciais próprias do serviço.')
    return {'name':plugin_name,'description':description,'kind':kind,'version':str(manifest.get('version','1.0.0'))[:40],'skills':skills,'servers':connections,'warnings':list(dict.fromkeys(warnings)),'files':files,'modes':modes,'digest':hashlib.sha256(data).hexdigest()}


def public_preview(package):
    return {k:package[k] for k in ['name','description','kind','version','skills','servers','warnings','digest']}|{'files':[{'path':p,'size':len(data)} for p,data in package['files'].items()]}|{'file_count':len(package['files']),'bytes':sum(len(v) for v in package['files'].values())}


def install_package(store,package):
    parent='import-'+uuid.uuid4().hex
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        instructions=package['skills'][0]['instructions'] if package['kind']=='skill' else ''
        db.execute('INSERT INTO imported_extensions(id,parent,kind,name,description,version,instructions,root,source) VALUES (?,?,?,?,?,?,?,?,?)',(parent,None,package['kind'],package['name'],package['description'],package['version'],instructions,'.',package.get('source','upload')))
        if package['kind']=='skill':db.execute('UPDATE imported_extensions SET implicit=? WHERE id=?',(int(package['skills'][0]['implicit']),parent))
        for path,data in package['files'].items():db.execute('INSERT INTO extension_files VALUES (?,?,?,?)',(parent,path,data,package['modes'][path]))
        if package['kind']=='plugin':
            for skill in package['skills']:
                key='import-'+uuid.uuid4().hex
                db.execute('INSERT INTO imported_extensions(id,parent,kind,name,description,version,instructions,root,source) VALUES (?,?,?,?,?,?,?,?,?)',(key,parent,'skill',skill['name'],skill['description'],package['version'],skill['instructions'],skill['root'],package.get('source','upload')))
                db.execute('UPDATE imported_extensions SET implicit=? WHERE id=?',(int(skill['implicit']),key))
        for server in package['servers']:
            key=uuid.uuid4().hex
            db.execute('INSERT INTO mcp_servers(id,package,name,config) VALUES (?,?,?,?)',(key,parent,server['name'],json.dumps(server['config'])))
    return parent


def materialize(store,package_id):
    root=store.directory/'extensions'/package_id
    if root.is_symlink() or (store.directory/'extensions').is_symlink():raise ValueError('Pasta de extensão inválida.')
    root.mkdir(parents=True,exist_ok=True,mode=0o700);base=root.resolve()
    if not base.is_relative_to(store.directory.resolve()):raise ValueError('Pasta de instalação fora dos dados do app.')
    with store.db() as db:files=db.execute('SELECT path,data,mode FROM extension_files WHERE package=?',(package_id,)).fetchall()
    for file in files:
        target=base/safe_path(file['path'])
        if not target.resolve().is_relative_to(base) or target.is_symlink():raise ValueError('Caminho de recurso inválido.')
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        # Atomic replacement also avoids following an existing final symlink.
        temp=target.parent/('.import-'+uuid.uuid4().hex)
        try:
            temp.write_bytes(file['data']);temp.chmod(file['mode']);os.replace(temp,target)
        finally:temp.unlink(missing_ok=True)
    return str(base)


def read_resource(store,skill_id,path,offset):
    if not isinstance(offset,int) or isinstance(offset,bool) or offset<0:raise ValueError('Offset inválido.')
    path=safe_path(path)
    with store.db() as db:
        skill=db.execute('SELECT * FROM imported_extensions WHERE id=? AND kind=\'skill\'',(skill_id,)).fetchone()
        if not skill:raise ValueError('Habilidade não encontrada.')
        root=skill['root'];full=str(PurePosixPath(root)/path)
        row=db.execute('SELECT data FROM extension_files WHERE package=? AND path=?',(skill['parent'] or skill_id,full)).fetchone()
    if not row:raise ValueError('Recurso não encontrado nesta habilidade.')
    try:text=row['data'].decode('utf-8')
    except UnicodeDecodeError as e:raise ValueError('Recurso binário: use o download do pacote para consultá-lo.') from e
    return {'path':path,'offset':offset,'total_characters':len(text),'text':text[offset:offset+4000]}


def prepare_script(store,args,options):
    import shutil
    from .agent_tools import prepare_action
    if options['kind']!='agent' or options['agent_mode']!='build':raise ValueError('Scripts só estão disponíveis no Agente Build.')
    path=safe_path(args['path']);values=args.get('args',[])
    if not isinstance(values,list) or len(values)>32 or any(not isinstance(v,str) or len(v)>4096 or '\x00' in v for v in values):raise ValueError('Argumentos do script inválidos.')
    with store.db() as db:
        row=db.execute("SELECT * FROM imported_extensions WHERE id=? AND kind='skill'",(args['id'],)).fetchone()
        if not row:raise ValueError('Habilidade não encontrada.')
        resource=str(PurePosixPath(row['root'])/path)
        if not db.execute('SELECT 1 FROM extension_files WHERE package=? AND path=?',(row['parent'] or row['id'],resource)).fetchone():raise ValueError('Script não pertence à habilidade.')
    root=materialize(store,row['parent'] or row['id']);folder=str(Path(root)/row['root']);file=Path(folder)/path
    programs={'.py':['python3','python'],'.js':['node'],'.mjs':['node'],'.cjs':['node'],'.ps1':['pwsh','powershell'],'.sh':['bash','sh']}
    choices=programs.get(file.suffix.lower())
    if os.name=='nt' and file.suffix.lower()=='.py':choices=['python','python3']
    if not choices:raise ValueError('Formato de script suportado: Python, JavaScript, PowerShell ou shell.')
    program=next((shutil.which(name) for name in choices if shutil.which(name)),None)
    if not program:raise ValueError('Instale o runtime necessário para executar este script.')
    argv=[program]+(['-File'] if file.suffix.lower()=='.ps1' else [])+[str(file)]+values
    action=prepare_action('run_command',{'argv':argv},options['kind'],options['agent_mode'],options['workspace'],options['internet'],options['access'])
    action.update(name='run_skill_script',arguments=args,summary=row['name']+' · '+json.dumps(argv,ensure_ascii=False),script_argv=argv,script_env=dict(os.environ,PLUGIN_ROOT=root,CLAUDE_PLUGIN_ROOT=root,SKILL_ROOT=folder))
    return action
