import argparse
import multiprocessing
import os
from pathlib import Path
import socket
import sqlite3
import sys
import threading
import time


def main():
    # A frozen extraction worker must exit through freeze_support before loading
    # FastAPI, opening the database, taking its lock or starting another UI.
    multiprocessing.freeze_support()
    from backend.runtime import build_info
    p=argparse.ArgumentParser(description='Central IA Studio — IA local Windows')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--no-browser',action='store_true')
    paths=p.add_mutually_exclusive_group()
    paths.add_argument('--data-dir')
    paths.add_argument('--portable',action='store_true',help='Dados em data junto ao EXE; exige escrita.')
    p.add_argument('--migrate-from',help='Copiar uma base antiga para um destino vazio, sem apagar a origem.')
    p.add_argument('--version',action='store_true')
    args=p.parse_args()
    try:
        build=build_info()
        if args.version:
            import json
            print(json.dumps(build,ensure_ascii=False));return 0
        if not 1<=args.port<=65535:raise ValueError('Porta inválida. Use um número de 1 a 65535.')
        sock=socket.socket()
        if os.name=='nt':sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        else:sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:sock.bind(('127.0.0.1',args.port))
        except OSError as error:
            sock.close();raise ValueError(f'Porta {args.port} ocupada. Feche a outra instância ou use --port com outra porta.') from error
        try:
            from backend.data_paths import resolve_data,DataLock
            from backend.process_guard import install_process_guard
            data,report=resolve_data(args.data_dir,args.portable,args.migrate_from)
            with DataLock(data):
                protection=install_process_guard(build['distribution']=='onefile')
                import uvicorn
                from backend.app import create_app
                app=create_app(data)
                app.state.runtime_details={'portable':args.portable,'migration':report,'process_guard':protection}
                config=uvicorn.Config(app,host='127.0.0.1',port=args.port,log_level='info',access_log=False)
                server=uvicorn.Server(config)
                app.state.request_shutdown=lambda:setattr(server,'should_exit',True)
                done=threading.Event()
                if not args.no_browser:
                    def open_ready():
                        import webbrowser
                        for _ in range(1800):
                            if done.wait(.05):return
                            if server.started:
                                webbrowser.open(f'http://127.0.0.1:{args.port}');return
                    threading.Thread(target=open_ready,name='central-browser',daemon=True).start()
                print(f"Central IA Studio {build['version']} · {build['commit'][:12]} · {build['distribution']}")
                print('Dados persistentes: '+str(data),flush=True)
                if report.get('notice'):print(report['notice'],flush=True)
                try:server.run(sockets=[sock])
                finally:done.set()
        finally:sock.close()
        return 0
    except (OSError,ValueError,sqlite3.Error) as error:
        print('Não foi possível iniciar o Central IA Studio: '+str(error),file=sys.stderr,flush=True)
        if os.name=='nt' and not args.no_browser and sys.stdin.isatty():
            try:input('Pressione Enter para fechar. Seus dados foram preservados. ')
            except (EOFError,KeyboardInterrupt):pass
        return 2


if __name__=='__main__':sys.exit(main())
