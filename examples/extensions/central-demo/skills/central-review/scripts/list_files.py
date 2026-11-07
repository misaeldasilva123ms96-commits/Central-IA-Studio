from pathlib import Path
for item in sorted(Path.cwd().iterdir(),key=lambda p:p.name)[:30]:
    print(('pasta: ' if item.is_dir() else 'arquivo: ')+item.name)
