"""Bounded, local tools for the bundled optional plugins. No eval, files or network."""
import ast
import csv
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation,localcontext
import io
import json
import math
import operator

NAMES={'calculate','format_json','summarize_csv','current_datetime'}


def utility_definitions():
    def make(name,description,properties,required):
        return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}}
    return [make('calculate','Calcular expressão aritmética (+ - * / // % **). Sem variáveis ou código.',{'expression':{'type':'string','maxLength':500}},['expression']),
            make('format_json','Validar e formatar texto JSON.',{'text':{'type':'string','maxLength':20000}},['text']),
            make('summarize_csv','Somar e resumir uma coluna numérica de CSV com cabeçalho. Informe separador e marca decimal.',{'text':{'type':'string','maxLength':20000},'column':{'type':'string'},'delimiter':{'type':'string','enum':[',',';','\t']},'decimal':{'type':'string','enum':['.',',']},'exclude_negative':{'type':'boolean'}},['text','column','delimiter','decimal']),
            make('current_datetime','Consultar a data/hora atual do computador em UTC.',{},[])]


def execute(name,args):
    if name=='current_datetime':return {'utc':datetime.now(timezone.utc).isoformat(),'timezone':'UTC'}
    if name=='calculate':
        expression=args.get('expression')
        if not isinstance(expression,str) or not 1<=len(expression)<=500:raise ValueError('Expressão deve ter até 500 caracteres.')
        try:tree=ast.parse(expression,mode='eval')
        except (SyntaxError,RecursionError) as error:raise ValueError('Expressão aritmética inválida.') from error
        if len(list(ast.walk(tree)))>80:raise ValueError('Expressão complexa demais.')
        operations={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
        def visit(node):
            if isinstance(node,ast.Constant) and type(node.value) in (int,float):value=float(node.value)
            elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):value=visit(node.operand)*(1 if isinstance(node.op,ast.UAdd) else -1)
            elif isinstance(node,ast.BinOp) and type(node.op) in operations:
                a,b=visit(node.left),visit(node.right)
                if isinstance(node.op,ast.Pow) and abs(b)>12:raise ValueError('Expoente excede o limite de 12.')
                value=operations[type(node.op)](a,b)
            else:raise ValueError('Use somente números e operadores aritméticos.')
            if not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1e100:raise ValueError('Resultado fora dos limites numéricos.')
            return value
        try:result=visit(tree.body)
        except (ArithmeticError,TypeError) as error:raise ValueError('Operação aritmética inválida: '+str(error)) from error
        return {'expression':expression,'result':result,'precision':'ponto flutuante'}
    text=args.get('text')
    if not isinstance(text,str) or len(text)>20000:raise ValueError('Texto limitado a 20.000 caracteres.')
    if name=='format_json':
        try:
            value=json.loads(text,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Número JSON inválido: '+x)))
            formatted=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
        except (ValueError,RecursionError) as error:raise ValueError('JSON inválido: '+str(error)) from error
        if len(formatted)>40000:raise ValueError('JSON formatado excede 40.000 caracteres.')
        return {'valid':True,'formatted':formatted}
    if name=='summarize_csv':
        delimiter=args.get('delimiter');decimal=args.get('decimal');column=args.get('column');exclude=args.get('exclude_negative',False)
        if delimiter not in [',',';','\t'] or decimal not in ['.',','] or not isinstance(column,str) or not isinstance(exclude,bool):raise ValueError('Informe coluna, separador, marca decimal e filtro válidos.')
        reader=csv.DictReader(io.StringIO(text),delimiter=delimiter,strict=True)
        if not reader.fieldnames or len(reader.fieldnames)>64 or len(set(reader.fieldnames))!=len(reader.fieldnames) or column not in reader.fieldnames:raise ValueError('Cabeçalho inválido ou coluna não encontrada.')
        values=[];invalid=negative=rows=0
        for row in reader:
            rows+=1
            if rows>1000:raise ValueError('CSV limitado a 1.000 linhas.')
            try:
                raw=(row.get(column) or '').strip()
                if decimal==',' and '.' in raw:raise InvalidOperation
                if decimal=='.' and ',' in raw:raise InvalidOperation
                number=Decimal(raw.replace(',','.'))
                if not number.is_finite() or number.copy_abs()>Decimal('1e50') or len(number.as_tuple().digits)>50 or number.as_tuple().exponent < -20:raise InvalidOperation
            except (InvalidOperation,ValueError):invalid+=1;continue
            if exclude and number<0:negative+=1;continue
            values.append(number)
        with localcontext() as context:
            context.prec=80
            total=sum(values,Decimal(0))
        return {'column':column,'rows':rows,'used':len(values),'invalid':invalid,'negative_excluded':negative,'sum':str(total),'min':str(min(values)) if values else None,'max':str(max(values)) if values else None}
    raise ValueError('Ferramenta desconhecida.')
