"""Bounded document ingestion; attachments live in SQLite and participate in backups."""
import base64
import hashlib
import io
import json
import time
import uuid
import warnings
from pathlib import PurePath
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from PIL import Image, ImageOps
from pypdf import PdfReader

MAX_FILE=8*1024*1024
MAX_TEXT=60000
TEXT_EXTENSIONS=set('txt md markdown csv tsv json jsonl yaml yml xml html htm css scss js jsx ts tsx py ipynb sql sh bash ps1 bat cmd c cpp h hpp java cs go rs rb php toml ini cfg conf log r tex'.split())
IMAGE_EXTENSIONS={'png','jpg','jpeg','webp','gif','bmp'}


def office_text(data,extension):
    with ZipFile(io.BytesIO(data)) as z:
        names=z.namelist()
        total=sum(info.file_size for info in z.infolist())
        if len(names)>2000 or total>20*1024*1024:
            raise ValueError('Documento Office excede o limite de extração (20 MiB).')
        def xml(name):
            raw=z.read(name)
            if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:
                raise ValueError('Documento XML com entidades não é aceito.')
            return ET.fromstring(raw)
        if extension=='docx':
            doc=xml('word/document.xml')
            return '\n'.join(''.join(p.itertext()) for p in doc.iter() if p.tag.endswith('}p'))
        shared=[]
        if 'xl/sharedStrings.xml' in names:
            shared=[''.join(s.itertext()) for s in xml('xl/sharedStrings.xml') if s.tag.endswith('}si')]
        rows=[]
        for name in sorted(n for n in names if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'))[:10]:
            rows.append('Planilha: '+name)
            for row in (e for e in xml(name).iter() if e.tag.endswith('}row')):
                cells=[]
                for cell in row:
                    text=''.join(cell.itertext())
                    if cell.attrib.get('t')=='s':
                        text=shared[int(text)]
                    cells.append(text)
                rows.append('\t'.join(cells))
                if len(rows)>=2000:return '\n'.join(rows)
        return '\n'.join(rows)


def ingest(name,data):
    # Paths from a browser must never become filesystem paths or response headers.
    name=name.replace('\\','/').split('/')[-1].strip()
    if not name or len(name)>180 or any(ord(c)<32 for c in name):
        raise ValueError('Nome de arquivo inválido (máximo de 180 caracteres).')
    if not data or len(data)>MAX_FILE:
        raise ValueError('Cada arquivo deve ter entre 1 byte e 8 MiB.')
    extension=name.rsplit('.',1)[-1].lower() if '.' in name else ''
    kind='document';mime='application/octet-stream';text='';warning='';vision=None
    try:
        if extension in IMAGE_EXTENSIONS:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    detected=image.format
                    if detected not in ['PNG','JPEG','WEBP','GIF','BMP']:raise ValueError('Formato real da imagem não é suportado.')
                    if image.width*image.height>20_000_000:raise ValueError('Imagem maior que 20 megapixels.')
                    image.seek(0)
                    image=ImageOps.exif_transpose(image).convert('RGB')
                    image.thumbnail((1600,1600))
                    out=io.BytesIO();image.save(out,format='JPEG',quality=88)
                    vision=out.getvalue()
            kind='image';mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp','GIF':'image/gif','BMP':'image/bmp'}[detected]
            warning='Original preservado. Para visão: até 1600 px, sem metadados e apenas o primeiro quadro de animações.'
        elif extension in TEXT_EXTENSIONS:
            try:text=data.decode('utf-8-sig')
            except UnicodeDecodeError:text=data.decode('cp1252')
            if '\x00' in text:raise ValueError('Arquivo binário não é texto legível.')
            mime='text/plain'
        elif extension=='pdf':
            pdf=PdfReader(io.BytesIO(data),strict=False)
            if pdf.is_encrypted:raise ValueError('PDF protegido por senha não é aceito.')
            if len(pdf.pages)>40:raise ValueError('PDF limitado a 40 páginas; divida o documento.')
            # Bound decoded page streams before invoking the text extractor.
            parts=[]
            for page in pdf.pages:
                contents=page.get_contents()
                if contents and len(contents.get_data())>4*1024*1024:
                    raise ValueError('Página PDF excede o limite de extração.')
                parts.append((page.extract_text() or '')[:MAX_TEXT])
                if sum(map(len,parts))>MAX_TEXT:break
            text='\n\n'.join(parts);mime='application/pdf'
            if not text.strip():warning='PDF sem texto extraível. OCR não está disponível; anexe as páginas como imagens a um modelo de visão.'
        elif extension in ['docx','xlsx']:
            text=office_text(data,extension)
            if extension=='xlsx':warning='Leitura XLSX limitada a 10 planilhas e 2.000 linhas.'
            mime='application/vnd.openxmlformats-officedocument.'+('wordprocessingml.document' if extension=='docx' else 'spreadsheetml.sheet')
        else:
            raise ValueError('Formato não suportado. Use texto/código, CSV, PDF, DOCX, XLSX ou PNG/JPEG/WebP/GIF/BMP.')
    except ValueError:raise
    except Exception as error:
        raise ValueError('Não foi possível ler este arquivo. Confira se o formato é válido.') from error
    if len(text)>MAX_TEXT:
        text=text[:MAX_TEXT];warning='Texto limitado aos primeiros 60.000 caracteres. Divida o documento para enviar o restante.'
    return {'id':uuid.uuid4().hex,'name':name,'mime':mime,'kind':kind,'size':len(data),
            'text':text,'data':data,'vision':vision,'warning':warning,'sha256':hashlib.sha256(data).hexdigest(),'created':time.time()}


def public_attachment(row):
    return {k:row[k] for k in ['id','name','mime','kind','size','warning','sha256']}


def model_message(store,message):
    items=message.get('attachments',[])
    if not items:return {'role':message['role'],'content':message['content']}
    text=message['content'];images=[]
    for item in items:
        with store.db() as db:
            row=db.execute('SELECT * FROM attachments WHERE id=?',(item['id'],)).fetchone()
        if row is None:raise ValueError('Anexo não encontrado no histórico.')
        if row['kind']=='image':
            images.append({'type':'image_url','image_url':{'url':'data:'+('image/jpeg' if row['vision'] else row['mime'])+';base64,'+base64.b64encode(row['vision'] or row['data']).decode()}})
        else:
            text+='\n\n<documento_anexado nome='+json.dumps(row['name'],ensure_ascii=False)+'>\n'+row['text'][:1000]+'\n</documento_anexado>'
            text+='\nID do anexo: '+row['id']+' · '+str(len(row['text']))+' caracteres extraídos. Use read_attachment/search_attachment para consultar o restante.'
            if row['warning']:text+='\nNota de extração: '+row['warning']
    content=[{'type':'text','text':text},*images] if images else text
    return {'role':message['role'],'content':content}


def _extract_worker(pipe,name,data):
    try:
        if __import__('os').name!='nt':
            import resource
            resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
        from pypdf import overwrite_configuration
        overwrite_configuration(maximum_declared_stream_length=8*1024*1024,zlib_maximum_output_length=4*1024*1024,
                                stream_decoding_work_maximum_length=8*1024*1024)
        pipe.send((True,ingest(name,data)))
    except BaseException as error:
        pipe.send((False,str(error) or 'Falha ao extrair documento.'))
    finally:pipe.close()


def extract(name,data):
    """Parser timeout is enforced by terminating an isolated worker, including on Windows."""
    import multiprocessing
    context=multiprocessing.get_context('spawn')
    reader,writer=context.Pipe(duplex=False)
    worker=context.Process(target=_extract_worker,args=(writer,name,data),daemon=True)
    worker.start();writer.close()
    try:
        if not reader.poll(20):raise ValueError('Extração excedeu 20 segundos. Divida o documento.')
        try:ok,result=reader.recv()
        except EOFError:raise ValueError('O extrator encerrou por limite de recursos ou arquivo inválido.')
        if not ok:raise ValueError('Não foi possível extrair o arquivo: '+result)
        return result
    finally:
        reader.close()
        worker.join(timeout=1)
        if worker.is_alive():worker.terminate();worker.join(timeout=3)
