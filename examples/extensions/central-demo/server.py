"""Tiny, local MCP demo using only Python's standard library. No files/network."""
import json
import sys

def respond(request):
    method=request.get('method');params=request.get('params') or {}
    if method=='initialize':return {'protocolVersion':params.get('protocolVersion','2025-11-25'),'capabilities':{'tools':{}},'serverInfo':{'name':'central-demo','version':'1.0.0'}}
    if method=='ping':return {}
    if method=='tools/list':return {'tools':[{'name':'demo_sum','description':'Somar dois inteiros no servidor de exemplo local.','inputSchema':{'type':'object','properties':{'a':{'type':'integer'},'b':{'type':'integer'}},'required':['a','b'],'additionalProperties':False}}]}
    if method=='tools/call':
        values=params.get('arguments',{})
        if params.get('name')!='demo_sum' or type(values.get('a')) is not int or type(values.get('b')) is not int:raise ValueError('Informe dois inteiros em demo_sum.')
        total=values['a']+values['b']
        return {'content':[{'type':'text','text':json.dumps({'total':total})}],'isError':False}
    raise ValueError('Método não suportado.')

for line in sys.stdin:
    try:
        request=json.loads(line)
        if not isinstance(request,dict) or 'id' not in request:continue
        try:response={'jsonrpc':'2.0','id':request['id'],'result':respond(request)}
        except (ValueError,TypeError,KeyError):response={'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':'Requisição inválida.'}}
        sys.stdout.write(json.dumps(response,ensure_ascii=True)+'\n');sys.stdout.flush()
    except (ValueError,TypeError):continue
