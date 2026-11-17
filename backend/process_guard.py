"""Keep manager-owned Windows descendants in a kill-on-close Job Object."""
import os
import sys
import threading

_job_handle=None  # retain until OS process teardown; never close a self-job early


def install_process_guard(onefile=False):
    global _job_handle
    if os.name!='nt':return {'enabled':False,'method':'owned process handles (POSIX)'}
    import ctypes as c
    from ctypes import wintypes as w
    class Limits(c.Structure):
        _fields_=[('process_time',c.c_longlong),('job_time',c.c_longlong),('flags',w.DWORD),('min_working_set',c.c_size_t),('max_working_set',c.c_size_t),('active_limit',w.DWORD),('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class Io(c.Structure):
        _fields_=[(name,c.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(c.Structure):
        _fields_=[('basic',Limits),('io',Io),('process_memory',c.c_size_t),('job_memory',c.c_size_t),('peak_process',c.c_size_t),('peak_job',c.c_size_t)]
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD];kernel.SetInformationJobObject.restype=w.BOOL
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    handle=kernel.CreateJobObjectW(None,None)
    if not handle:raise OSError('Não foi possível criar a proteção dos processos: '+str(c.WinError(c.get_last_error())))
    limits=Extended();limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle,9,c.byref(limits),c.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess()):
        error=c.get_last_error();kernel.CloseHandle(handle)
        raise OSError('Não foi possível proteger a árvore de processos do Central: '+str(c.WinError(error)))
    _job_handle=handle
    if onefile:
        # The onefile bootloader is a separate parent. Its forced termination must
        # not leave the Python child (and consequently the engine) running.
        kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
        kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
        parent=kernel.OpenProcess(0x100000,False,os.getppid())
        if not parent:raise OSError('Não foi possível acompanhar o processo inicializador do ONEFILE.')
        def watch():
            if kernel.WaitForSingleObject(parent,0xFFFFFFFF)==0:os._exit(3)
        threading.Thread(target=watch,name='central-bootloader-watch',daemon=True).start()
    return {'enabled':True,'method':'Windows Job Object','parent_watch':onefile}
