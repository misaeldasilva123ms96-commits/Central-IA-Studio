"""Fail closed unless both frozen distributions and their interchange pass."""
import json
import os
from pathlib import Path
import platform
import statistics
import sys
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from scripts.test_windows_distribution import App
import psutil


def main():
    results=[json.loads((ROOT/f'work/test-{mode}.json').read_text()) for mode in ('onedir','onefile')]
    assert all(r.get('passed') for r in results),results
    a,b=results
    for key in ('version','commit','schema','payload_digest','engine_sha256','resources'):assert a['build'][key]==b['build'][key],key
    assert a['model_sha256']==b['model_sha256'] and a['model_path']==b['model_path']
    assert a['features']==b['features'] and a['cross_data_directory']==b['cross_data_directory']
    # Read data written by ONEFILE back through ONEDIR, with no file copying.
    env=os.environ.copy();env['LOCALAPPDATA']=str(ROOT/'work/cross-distribution-profile')
    app=App(ROOT/'work/smoke onedir/application with spaces/CentralIAStudio/CentralIAStudio.exe',env,ROOT/'work/cross-back-to-onedir')
    try:
        titles={c['title'] for c in app.api('/api/conversations')}
        assert {'Intercâmbio onedir','Intercâmbio onefile'}<=titles
        assert app.api('/api/profiles')['temperature']==.33
    finally:app.close()
    checks={'passed':True,'version':a['build']['version'],'commit':a['build']['commit'],'schema':a['build']['schema'],'payload_digest':a['build']['payload_digest'],'bidirectional_shared_data':True,'distributions':results}
    (ROOT/'TEST_RESULTS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    measured={'version':checks['version'],'commit':checks['commit'],'host':{'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':psutil.cpu_count(),'physical_cpus':psutil.cpu_count(logical=False),'ram_bytes':psutil.virtual_memory().total},'limitations':['Two launches per format; OS caches are not forcibly cleared.','The GGUF is tiny, random and untrained; results do not certify user models or target i5 hardware.','RSS is per process; USS is private bytes, browser JS heap is not total browser RAM.','Onefile extraction before Python and leftover temp after forced bootloader death are PyInstaller constraints.'],'optimizations':json.loads((ROOT/'work/optimization-measurements.json').read_text()),'formats':{}}
    for result in results:
        measured['formats'][result['format']]={key:result[key] for key in ('distributed_bytes','installed_bytes','samples','forced_exit_temp_remains')}
    (ROOT/'BUILD_REPORT.json').write_text(json.dumps(measured,indent=2),encoding='utf-8')
    print('Both distributions passed; version/commit/resources/schema match; bidirectional shared data verified.')

if __name__=='__main__':main()
