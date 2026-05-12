import re, glob, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for path in sorted(glob.glob('tests/*.spec.ts')):
    s = open(path, encoding='utf-8').read()
    new = re.sub(r"goto\('/([a-z-]+\.html)", r"goto('/workhive/\1", s)
    new = re.sub(r"smokePage\(whPage, '/([a-z-]+\.html)", r"smokePage(whPage, '/workhive/\1", new)
    if new != s:
        open(path, 'w', encoding='utf-8', newline='\n').write(new)
        print(f'updated {path}')
