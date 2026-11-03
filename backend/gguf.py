"""Leitura limitada de metadados GGUF v2/v3, sem carregar tensores."""
import struct
from pathlib import Path

TYPES = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
FILE_TYPES = {0:'F32',1:'F16',2:'Q4_0',3:'Q4_1',7:'Q8_0',8:'Q5_0',9:'Q5_1',10:'Q2_K',11:'Q3_K_S',12:'Q3_K_M',13:'Q3_K_L',14:'Q4_K_S',15:'Q4_K_M',16:'Q5_K_S',17:'Q5_K_M',18:'Q6_K',30:'BF16'}

def metadata(path):
    with open(path, 'rb') as f:
        def read(n):
            if n < 0 or n > 8*1024*1024 or f.tell()+n > 64*1024*1024:
                raise ValueError('Cabeçalho GGUF excede limite de leitura de 64 MiB')
            b = f.read(n)
            if len(b) != n:
                raise ValueError('Cabeçalho GGUF truncado')
            return b
        def number(fmt):
            return struct.unpack('<'+fmt, read(struct.calcsize('<'+fmt)))[0]
        def string():
            n = number('Q')
            return read(n).decode('utf-8', errors='replace')
        def value(t, depth=0):
            if depth > 2:
                raise ValueError('Metadados aninhados excessivos')
            if t in TYPES:
                return number(TYPES[t])
            if t == 8:
                return string()
            if t == 9:
                subtype, count = number('I'), number('Q')
                if count > 2000000:
                    raise ValueError('Array GGUF excessivo')
                # Arrays de tokens são descartados sem alocação proporcional.
                if subtype in TYPES:
                    n = struct.calcsize('<'+TYPES[subtype])*count
                    if f.tell()+n > min(Path(path).stat().st_size,64*1024*1024):
                        raise ValueError('Array truncado ou excessivo')
                    f.seek(n, 1)
                else:
                    for _ in range(count):
                        value(subtype, depth+1)
                return None
            raise ValueError('Tipo GGUF desconhecido')
        if read(4) != b'GGUF':
            raise ValueError('Assinatura GGUF inválida')
        version = number('I')
        if version not in [2,3]:
            raise ValueError('Somente GGUF v2/v3 little endian')
        tensors, count = number('Q'), number('Q')
        if count > 100000:
            raise ValueError('Quantidade de metadados excessiva')
        result = {'gguf_version':version,'tensors':tensors}
        for _ in range(count):
            key = string()
            v = value(number('I'))
            if v is not None and (key.startswith('general.') or key.endswith('.context_length') or key == 'tokenizer.chat_template'):
                result[key] = v
        result['quantization'] = FILE_TYPES.get(result.get('general.file_type'), 'Não identificada')
        template = result.pop('tokenizer.chat_template', '')
        result['has_template'] = bool(template)
        result['thinking_switch_in_template'] = 'enable_thinking' in template
        return result

def discover(folders):
    found, errors, seen = [], [], set()
    for folder in folders:
        root = Path(folder).resolve()
        if not root.is_dir():
            errors.append({'path':str(root),'error':'Pasta indisponível'})
            continue
        for path in root.rglob('*'):
            if path.suffix.lower() != '.gguf' or not path.is_file():
                continue
            try:
                path = path.resolve()
                if not path.is_relative_to(root) or str(path) in seen:
                    continue
                seen.add(str(path))
                item = {'path':str(path),'name':path.name,'size':path.stat().st_size}
                try:
                    item['metadata'] = metadata(path)
                    item['status'] = 'Metadados lidos; inferência não validada'
                except (ValueError,OSError,struct.error) as e:
                    item['metadata'] = {}
                    item['status'] = 'GGUF inválido ou não suportado: '+str(e)
                found.append(item)
            except OSError as e:
                errors.append({'path':str(path),'error':str(e)})
    return {'models':sorted(found,key=lambda m:m['name'].lower()),'errors':errors}
