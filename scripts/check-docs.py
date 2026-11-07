"""Check maintained document entry points and their local file links."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
PRIORITY=['README.md','AGENTS.md','docs/architecture.md','docs/installation.md','docs/configuration.md','docs/usage.md','docs/operations.md','docs/contributing.md','docs/security.md','docs/repository-layout.md','docs/maintenance-audit.md']
PRIORITY += ['docs/store-status-home.md','docs/zh-CN/store-status-home.md']
PRIORITY += ['docs/emag-playbooks.md','docs/zh-CN/emag-playbooks.md','docs/emag-market-research.md','docs/zh-CN/emag-market-research.md']
PRIORITY += [f'docs/zh-CN/{name}.md' for name in ('readme','architecture','installation','configuration','usage','operations')]


def check():
    errors=[]
    for name in PRIORITY:
        path=ROOT/name
        if not path.is_file():errors.append(f'Missing document: {name}');continue
        text=re.sub(r'```.*?```','',path.read_text('utf-8'),flags=re.S)
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            target=target.strip().split('#',1)[0]
            if not target or '://' in target or target.startswith(('mailto:','data:')):continue
            if not (path.parent/unquote(target)).is_file():errors.append(f'{name}: missing link target {target}')
    return errors


if __name__=='__main__':
    issues=check()
    for issue in issues:print(issue,file=sys.stderr)
    if issues:raise SystemExit(1)
    print(f'Document links passed for {len(PRIORITY)} maintained entry points.')
