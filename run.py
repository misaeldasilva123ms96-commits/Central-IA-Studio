import os
import argparse
import multiprocessing
import socket
import sys
import threading
import webbrowser
from pathlib import Path
import uvicorn
from backend.app import create_app

def main():
    multiprocessing.freeze_support()
    p = argparse.ArgumentParser(description='Central IA Studio — gerenciador local')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--no-browser',action='store_true')
    p.add_argument('--data-dir',default=str(Path(sys.executable).resolve().parent/'data') if getattr(sys,'frozen',False) else None)
    args = p.parse_args()
    try:
        with socket.socket() as s:
            if os.name == 'nt':
                s.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            else:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            s.bind(('127.0.0.1',args.port))
    except OSError:
        print(f'Porta {args.port} ocupada. Feche a outra instância ou use --port com outra porta.')
        return 1
    app = create_app(args.data_dir)
    if not args.no_browser:
        threading.Timer(1.2,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='info',access_log=False)
    return 0

if __name__ == '__main__':
    sys.exit(main())
