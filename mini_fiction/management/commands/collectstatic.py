#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
from hashlib import sha256
from datetime import datetime

import click
from flask import current_app

from mini_fiction.management.manager import cli


def collect_files(src, only=None, ignore=None, follow_symlinks=False):
    only = frozenset(only or ())
    ignore = frozenset(ignore or ())
    result = []

    queue = os.listdir(src)
    queue.sort(reverse=True)
    while queue:
        path = queue.pop()
        abspath = os.path.join(src, path)

        if (not follow_symlinks and os.path.islink(abspath)) or os.path.isfile(abspath):
            if only and path not in only:
                continue
            if path not in ignore:
                result.append(path)
            continue

        assert os.path.isdir(abspath)

        if path not in ignore and os.path.join(path, '') not in ignore:
            q = [os.path.join(path, x) for x in os.listdir(abspath)]
            q.sort(reverse=True)
            queue.extend(q)

    return result


def copyfile(src, dst, global_hash, follow_symlinks=False, verbose=True):
    if verbose:
        print(dst, end='', flush=True)

    dstdir = os.path.dirname(dst)
    if not os.path.isdir(dstdir):
        os.makedirs(dstdir)  # TODO: что-то сделать с правами

    if not follow_symlinks and os.path.islink(src):
        changed = False
        if not os.path.islink(dst) or os.readlink(src) != os.readlink(dst):
            if os.path.exists(dst):
                os.remove(dst)
            os.symlink(os.readlink(src), dst)
            changed = True
        if verbose:
            print(' (symlink)', flush=True)
        return changed

    old_hash = None
    if os.path.isfile(dst):
        old_hash_obj = sha256()
        with open(dst, 'rb') as fp:
            while True:
                chunk = fp.read(16384)
                if not chunk:
                    break
                old_hash_obj.update(chunk)
        old_hash = old_hash_obj.hexdigest()
        del old_hash_obj

    new_hash_obj = sha256()
    with open(src, 'rb') as fp:
        while True:
            chunk = fp.read(16384)
            if not chunk:
                break
            new_hash_obj.update(chunk)
            global_hash.update(chunk)
    new_hash = new_hash_obj.hexdigest()
    del new_hash_obj

    if old_hash != new_hash:
        shutil.copy2(src, dst)
        if verbose:
            print(' (updated)', flush=True)
        return True

    if verbose:
        print(' (not changed)', flush=True)
    return False

@cli.command(short_help='Copies static files.', help='Copies static files to DESTINATION directory (STATIC_ROOT by default).')
@click.option('-v/-V', '--verbose/--no-verbose', default=True)
@click.argument('destination', nargs=1, required=False)
def collectstatic(verbose, destination):
    modulestatic = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname((__file__)))), 'static')
    assert os.path.isdir(modulestatic)
    if verbose:
        print('Module static folder: {}'.format(modulestatic))

    projectstatic = os.path.abspath(destination or current_app.config['STATIC_ROOT'])
    if modulestatic == projectstatic:
        if verbose:
            print('Project static folder is the same.')
        return

    if verbose:
        print('Project static folder: {}'.format(projectstatic))

    copy_static_directory(
        modulestatic, projectstatic, verbose=verbose,
        static_version_file=current_app.config.get('STATIC_VERSION_FILE'),
        follow_symlinks=True,
    )


def copy_static_directory(
    src, dst, verbose=True, static_version_file=None,
    only=None, ignore=None, follow_symlinks=False
):
    modulestatic = src
    projectstatic = dst

    if not os.path.isdir(projectstatic):
        os.makedirs(projectstatic)
        shutil.copystat(modulestatic, projectstatic)

    if verbose:
        print('Collect files list...', end=' ', flush=True)
    srcfiles = collect_files(modulestatic, only=only, ignore=ignore, follow_symlinks=follow_symlinks)
    if verbose:
        print('found {} files.'.format(len(srcfiles)), flush=True)

    global_hash = sha256()
    changed_cnt = 0

    for path in srcfiles:
        src = os.path.join(modulestatic, path)
        dst = os.path.join(projectstatic, path)
        if copyfile(src, dst, global_hash=global_hash, verbose=verbose, follow_symlinks=follow_symlinks):
            changed_cnt += 1

    if verbose:
        print('{} files updated.'.format(changed_cnt))

    if changed_cnt > 0 and static_version_file:
        version_file_path = os.path.join(projectstatic, static_version_file)
        if not os.path.isdir(os.path.dirname(version_file_path)):
            os.makedirs(os.path.dirname(version_file_path))

        old_ver = None
        if os.path.isfile(version_file_path):
            with open(version_file_path, 'r', encoding='utf-8') as fp:
                old_ver = fp.read().strip()

        if current_app.config.get('STATIC_VERSION_TYPE') == 'date':
            new_ver = datetime.now().strftime('%Y%m%d')
            if new_ver == old_ver:
                new_ver += '.1'
        elif current_app.config.get('STATIC_VERSION_TYPE') == 'hash':
            new_ver = global_hash.hexdigest()[:8]

        if old_ver != new_ver:
            with open(version_file_path, 'w', encoding='utf-8') as fp:
                fp.write(new_ver + '\n')

    return changed_cnt
