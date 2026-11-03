"""Patch mínimo e verificável sobre a revisão imutável MIT do llama.cpp."""
import subprocess
import sys
from pathlib import Path

COMMIT = 'd1044bc82712fbf08996080bef6298b24a27e9c7'
root = Path(sys.argv[1]).resolve()
actual = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
if actual != COMMIT:
    raise RuntimeError('Revisão upstream diferente da revisão auditada: '+actual)
# Reconstrói sempre da fonte Git, sem acumular patches em reconfigurações.
source = subprocess.check_output(['git','-C',str(root),'show',COMMIT+':tools/server/server.cpp']).decode()
include = '#include "server-stream.h"'
marker = 'static void server_register_routes(server_http_context & ctx_http, server_routes & routes) {'
if source.count(include) != 1 or source.count(marker) != 1:
    raise RuntimeError('Contrato upstream alterado; revise o patch antes de compilar')
source = source.replace(include,include+'\n#include "central_routes.h"').replace(marker,marker+'\n    central_register_routes(ctx_http, routes);')
path = root/'tools/server/server.cpp'
if path.read_text() != source:
    path.write_text(source,encoding='utf-8')

# Ignore implicit system configuration and upstream environment options. Central's
# validated CLI is the complete startup contract (no tools/MCP from hidden config).
arg = subprocess.check_output(['git','-C',str(root),'show',COMMIT+':common/arg.cpp']).decode()
for old,new in [
    ('    common_params_apply_system_config(params, ctx_arg.ex);','    // Central Engine: no implicit llama.cpp system configuration.'),
    ('        if (opt.get_value_from_env(value)) {','        if (false && opt.get_value_from_env(value)) {')]:
    if arg.count(old) != 1:
        raise RuntimeError('Contrato de configuracao upstream alterado')
    arg = arg.replace(old,new)
arg_path = root/'common/arg.cpp'
if arg_path.read_text() != arg:
    arg_path.write_text(arg,encoding='utf-8')
