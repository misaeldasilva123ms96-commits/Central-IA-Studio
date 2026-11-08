"""Local, real MCP server used by deterministic integration tests."""
import asyncio
import os
import sys
from mcp.server.fastmcp import FastMCP
server=FastMCP('Central MCP fixture',host='127.0.0.1',port=int(sys.argv[2]) if len(sys.argv)>2 else 9999,stateless_http=True)

@server.tool()
def sum_values(x:int,y:int)->dict:
    return {'total':x+y}

@server.tool()
async def wait_for_stop()->str:
    await asyncio.sleep(60)
    return 'not expected'

@server.tool()
def credential_present()->dict:
    return {'present':bool(os.environ.get('PRIVATE_MCP_TOKEN'))}

if __name__=='__main__':
    if '--http' in sys.argv:
        import uvicorn
        from starlette.responses import JSONResponse
        app=server.streamable_http_app()
        @app.middleware('http')
        async def require_token(request,call_next):
            if request.headers.get('authorization')!='Bearer test-session-only':return JSONResponse({'error':'unauthorized'},status_code=401)
            return await call_next(request)
        uvicorn.run(app,host='127.0.0.1',port=int(sys.argv[2]),log_level='warning')
    else:server.run(transport='stdio')
