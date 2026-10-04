import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


def git(folder, *arguments, input=None):
    result = subprocess.run(
        ['git', '-C', str(folder), *arguments], input=input,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout.decode('utf-8').strip()


def local_path(folder, name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '\\' in name or ':' in name
            or any(part in ('.', '..') or part.lower() == '.git' for part in name.split('/'))):
        raise RuntimeError('Invalid patch path: ' + name)
    result = folder.joinpath(*path.parts).resolve()
    if not result.is_relative_to(folder.resolve()):
        raise RuntimeError('Patch path leaves its target directory: ' + name)
    return result


def patch_files(data):
    blocks = re.split(r'(?m)^diff --git ', data.decode('utf-8'))
    if blocks[0] or len(blocks) == 1:
        raise RuntimeError('Expected a full-index Git patch.')
    files = []
    for block in blocks[1:]:
        header = re.match(r'a/(\S+) b/(\S+)\n', block)
        index = re.search(r'(?m)^index ([0-9a-f]{40})\.\.([0-9a-f]{40}) (100644|100755)$', block)
        if not header or header[1] != header[2] or not index:
            raise RuntimeError('Only full-index regular-file modifications are supported.')
        name = header[1]
        if ('\n--- a/' + name + '\n+++ b/' + name + '\n@@ ' not in block
                or any(index[i] == '0' * 40 for i in (1, 2))
                or re.search(r'(?m)^(old mode|new mode|rename |copy |GIT binary patch)', block)):
            raise RuntimeError('Unsupported patch operation: ' + name)
        files.append((name, index[1], index[2]))
    return files


def plans(root):
    manifest = root / 'patches/submodules/series.json'
    entries = json.loads(manifest.read_text(encoding='utf-8'))['patches']
    result = []
    seen = set()
    for entry in entries:
        module = local_path(root, entry['module'])
        if not (module / '.git').exists():
            raise RuntimeError('Initialize submodule first: ' + entry['module'])
        if Path(git(module, 'rev-parse', '--show-toplevel')).resolve() != module:
            raise RuntimeError('Not the expected submodule repository: ' + entry['module'])
        revision = entry['revision']
        if not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise RuntimeError('Expected a full module revision.')
        pin = git(root, 'ls-tree', 'HEAD', '--', entry['module']).split()
        if pin[:3] != ['160000', 'commit', revision]:
            raise RuntimeError('Parent module pin changed: ' + entry['module'])
        if git(module, 'rev-parse', 'HEAD') != revision:
            raise RuntimeError('Module revision changed: ' + entry['module'])
        patch = local_path(root / 'patches/submodules' / entry['module'], entry['patch'])
        data = patch.read_bytes().replace(b'\r\n', b'\n')
        files = patch_files(data)
        states = set()
        for name, before, after in files:
            target = local_path(module, name)
            key = str(target).lower() if sys.platform == 'win32' else str(target)
            if key in seen:
                raise RuntimeError('Combine overlapping patches for: ' + name)
            seen.add(key)
            if not target.is_file():
                raise RuntimeError('Missing patch target: ' + str(target))
            actual = git(module, 'hash-object', '--path=' + name, '--', str(target))
            if actual == before:
                states.add('pending')
            elif actual == after:
                states.add('applied')
            else:
                raise RuntimeError('Unexpected contents in patch target: ' + str(target))
        if len(states) != 1:
            raise RuntimeError('Patch is only partially applied: ' + str(patch))
        pending = states == {'pending'}
        if pending:
            git(module, 'apply', '--check', '-', input=data)
        result.append((module, patch, data, files, pending))
    return result


def run(root, check=False, print_files=False):
    root = Path(root).resolve()
    pending_plans = plans(root)
    missing = [str(patch.relative_to(root)) for _, patch, _, _, pending in pending_plans if pending]
    if check and missing:
        raise RuntimeError('Required patches are missing: ' + ', '.join(missing)
                           + '\nRun: python "' + str(root / 'Telegram/build/apply_submodule_patches.py') + '"')
    for module, patch, data, files, pending in pending_plans:
        if pending:
            original = {name: local_path(module, name).read_bytes() for name, _, _ in files}
            try:
                git(module, 'apply', '-', input=data)
                for name, _, after in files:
                    if git(module, 'hash-object', '--path=' + name, '--', str(local_path(module, name))) != after:
                        raise RuntimeError('Applied patch has unexpected contents: ' + name)
            except Exception:
                for name, content in original.items():
                    local_path(module, name).write_bytes(content)
                raise
        if print_files:
            for name, _, _ in files:
                print(local_path(module, name).as_posix())
        else:
            print(('Applied: ' if pending else 'Already applied: ') + str(patch.relative_to(root)))


def main():
    parser = argparse.ArgumentParser(description='Apply the reviewed submodule patches, or verify them without changes.')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--print-files', action='store_true')
    arguments = parser.parse_args()
    try:
        run(Path(__file__).resolve().parents[2], arguments.check, arguments.print_files)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print('Submodule patches: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
