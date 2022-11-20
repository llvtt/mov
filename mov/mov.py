#!/usr/bin/python3.4

import argparse
import datetime
import os
import platform
import re
import shutil
import string
import sys
import tarfile

try:
    import cPickle as pickle
except ImportError:
    import pickle

import requests

from bs4 import BeautifulSoup

# Influential environment variables
INSTALL_ROOT = os.environ.get(
    'MOV_INSTALL_DIR', os.path.join(os.path.expanduser('~'), 'local'))

# Constants
MOV_DIR = os.path.join(INSTALL_ROOT, 'mov')
MOV_MONGODB_DIR = os.path.join(MOV_DIR, 'versions')
MOV_BIN_DIR = os.path.join(MOV_DIR, 'bin')
DOWNLOAD_URL_TEMPLATE = string.Template(
    'http://downloads.mongodb.org/$os/mongodb-$os-$arch-$version.$ext')
DIRECTORY_NAME_TEMPLATE = string.Template('mongodb-$os-$arch-$version')
LIST_URL_TEMPLATE = string.Template(
    'http://dl.mongodb.org/dl/$os')
ARCHITECTURE = platform.processor()
CURRENT_VERSION_FILE = os.path.join(MOV_DIR, 'version.current')
MANIFEST_FILE = os.path.join(MOV_DIR, 'version.manifest')
CACHE_EXPIRE_DAYS = 1
OS_MAP = {
    'Linux': 'linux',
    'Win32': 'win32',
    'Darwin': 'osx'
}
FILE_EXT_MAP = {
    'Linux': 'tgz',
    'Win32': 'zip',
    'Darwin': 'tgz'
}
try:
    OS = OS_MAP[platform.system()]
except KeyError:
    print('Your operating system %s is unsupported at this time.'
          % platform.system())
    sys.exit(1)


def __die(message, status=1):
    print(message)
    sys.exit(status)


def __rm_noerror(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _ensure_file(*paths):
    if len(paths) == 1 and os.path.isabs(paths[0]):
        path, _ = os.path.split(paths[0])
    else:
        path = os.path.join(MOV_DIR, *paths[:-1])
    if not os.path.exists(path):
        os.makedirs(path)
    return os.path.join(MOV_DIR, *paths)


if OS == 'win32':
    def unarchive(file_path):
        pass
else:
    def unarchive(file_path):
        destination, _ = os.path.split(file_path)
        try:
            with tarfile.open(file_path) as archive:
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner=numeric_owner) 
                    
                
                safe_extract(archive, destination)
        except tarfile.TarError as e:
            __die('Could not extract files from %s: %s'
                  % (file_path, str(e)), status=3)


_LINK_PATTERN = re.compile(ARCHITECTURE + r'-[^-]+\.')
def _filter_download_link(link):
    return (link is not None and
            'latest' not in link and
            re.search(_LINK_PATTERN, link))


def _cache_links(links):
    manifest = _ensure_file(MANIFEST_FILE)
    with open(manifest, 'wb') as fd:
        # Save versions dict with current date.
        pickle.dump((datetime.datetime.now(), links), fd)


def _get_cached_links():
    manifest = _ensure_file(MANIFEST_FILE)
    try:
        with open(manifest, 'rb') as fd:
            try:
                date_saved, versions = pickle.load(fd)
            except Exception:
                __die('Could not read manifest file; it may be corrupt.')
    except IOError:
        # File may not exist.
        return None
    expiry_date = datetime.datetime.now() - datetime.timedelta(
        days=CACHE_EXPIRE_DAYS)
    if expiry_date > date_saved:
        # Cache file too old.
        os.unlink(manifest)
        return None
    return versions


def _bin_dir(version):
    """Check if the 'bin' directory exists for a ``version`` of MongoDB."""
    src_dir_name = DIRECTORY_NAME_TEMPLATE.substitute(
        os=OS, arch=ARCHITECTURE, version=version)
    src_dir_path = os.path.join(MOV_MONGODB_DIR, version, src_dir_name, 'bin')
    return src_dir_path if os.path.exists(src_dir_path) else None


_VERSION_PATTERN = re.compile(r'v?(\d\.)+\d[^.]*')
def available_versions(use_cached=True):
    links = {}
    if use_cached:
        links = _get_cached_links() or {}
    if not links:
        list_url = LIST_URL_TEMPLATE.substitute(os=OS)
        response = requests.get(list_url)
        soup = BeautifulSoup(response.content)
        for row in soup.find_all('tr'):
            a_tag = row.find('a')
            if a_tag is not None and _filter_download_link(a_tag['href']):
                href = a_tag['href']
                match = re.search(_VERSION_PATTERN, href)
                links[match.group(0)] = href
        _cache_links(links)
    return links


def installed_versions():
    versions = []
    for version_dir in os.listdir(MOV_MONGODB_DIR):
        # Only directories with 'bin' directory inside count.
        if _bin_dir(version_dir):
            versions.append(version_dir)
    return versions


def switch_version(version):
    """Switch to using ``version`` of MongoDB."""
    # TODO: Windows support.
    __rm_noerror(MOV_BIN_DIR)
    bin_path = _bin_dir(version)
    if not bin_path:
        __die('No such directory %s while switching to version %s.'
              % (bin_path, version), status=4)
    os.symlink(bin_path, MOV_BIN_DIR)
    with open(_ensure_file(CURRENT_VERSION_FILE), 'w') as fd:
        fd.write(version)


def install_version(version):
    archive_url = DOWNLOAD_URL_TEMPLATE.substitute(
        os=OS, arch=ARCHITECTURE, version=version,
        ext=FILE_EXT_MAP[platform.system()])
    _, file_name = archive_url.rsplit('/', 1)

    sys.stdout.write('Downloading %s...' % archive_url)
    sys.stdout.flush()
    response = requests.get(archive_url, stream=True)
    if response.status_code >= 400:
        __die('Got status code %d when trying to retrieve:\n  %s'
              % (response.status_code, archive_url), status=2)

    file_path = _ensure_file(MOV_MONGODB_DIR, version, file_name)
    total_size = response.headers.get('Content-Length')
    if total_size is not None:
        total_size = float(total_size)
    bytes_read = 0
    with open(file_path, 'wb') as fd:
        for chunk in response.iter_content(1024 * 4):
            fd.write(chunk)
            if total_size is not None:
                bytes_read += len(chunk)
                sys.stdout.write(
                    '\rDownloading %s...%2.2f%%'
                    % (archive_url, 100 * bytes_read / total_size))
            else:
                # Using bytes_read as a counter.
                bytes_read += 1
                if bytes_read % 10 == 0:
                    sys.stdout.write('.')
                    sys.stdout.flush()
    print('')
    unarchive(file_path)
    switch_version(version)


def current_version():
    with open(_ensure_file(CURRENT_VERSION_FILE), 'r') as fd:
        return fd.read()


def latest_version(installed=False):
    if installed:
        versions = installed_versions()
        if not versions:
            __die('No versions of MongoDB are installed.', status=5)
    else:
        versions = available_versions()
    return sorted(versions)[-1]


def handle_list_versions(args):
    if args.active:
        print(current_version())
    else:
        this_version = current_version()

        def annotate_version(version):
            if version == this_version:
                return '* ' + version
            return '  ' + version
        if args.installed:
            listing = installed_versions()
        else:
            listing = available_versions(use_cached=not args.force)
        print('\n'.join(map(annotate_version, sorted(listing))))


def handle_install_version(args):
    install_version(version=args.version)


def handle_use_version(args):
    if args.version == 'latest':
        version = latest_version(installed=args.only_installed)
    else:
        version = args.version
    if _bin_dir(version):
        # Already installed; just switch version + return.
        switch_version(version)
    elif not args.only_installed:
        # Same as installing it.
        install_version(version=version)
    else:
        __die('MongoDB %s is not installed.' % version, status=100)


def handle_remove_version(args):
    if _bin_dir(args.version):
        if args.version == current_version():
            __rm_noerror(MOV_BIN_DIR)
            __rm_noerror(CURRENT_VERSION_FILE)
        shutil.rmtree(os.path.join(MOV_MONGODB_DIR, args.version))
    else:
        __die('MongoDB %s is not installed.' % args.version, status=100)


def main():
    parser = argparse.ArgumentParser(
        prog='mov',
        description='Version manager for MongoDB')

    subparsers = parser.add_subparsers()

    list_parser = subparsers.add_parser(
        'list', help='List versions of MongoDB')
    list_parser.set_defaults(func=handle_list_versions)
    list_parser.add_argument(
        '-i', '--installed', action='store_true', dest='installed',
        help='List only installed versions.')
    list_parser.add_argument(
        '-a', '--active', action='store_true', dest='active',
        help='Only display the active version.')
    list_parser.add_argument(
        '-f', '--force', action='store_true', dest='force',
        help='Force refresh of version information.')

    use_parser = subparsers.add_parser(
        'use', help='Switch to a different version of MongoDB')
    use_parser.set_defaults(func=handle_use_version)
    use_parser.add_argument(
        '-o', '--only-installed', action='store_true', dest='only_installed',
        help='Do not download the version if it is not already installed.')
    use_parser.add_argument('version', help='The version to use')

    remove_parser = subparsers.add_parser(
        'remove', help='Remove versions of MongoDB.')
    remove_parser.set_defaults(func=handle_remove_version)
    remove_parser.add_argument(
        '-a', '--all', action='store_true', dest='all',
        help='Remove all currently installed versions of MongoDB.')
    remove_parser.add_argument('version', help='The version to remove')

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
