"""Appending adds bytes to the end of the same file and syncs them, and the directory for a new file."""

import os
import stat
from unittest.mock import patch

import pytest

from surprisals_experiment.sdk.utils.append import append


@pytest.mark.parametrize('content, expected', [
    ('line\n', b'line\n'),
    (b'bytes\x00\xff', b'bytes\x00\xff'),
    ('café \U0001f600\n', 'café \U0001f600\n'.encode()),
    ('crlf\r\nkept\r\n', b'crlf\r\nkept\r\n'),
])
def test_creates_a_missing_file(tmp_path, content, expected):
    path = tmp_path / 'log.jsonl'
    append(path, content)
    assert path.read_bytes() == expected


def test_does_not_create_a_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        append(tmp_path / 'missing' / 'log.jsonl', 'line\n')
    assert not (tmp_path / 'missing').exists()


@pytest.mark.parametrize('content, expected', [
    ('second\n', b'first\nsecond\n'),
    (b'\x00\xff', b'first\n\x00\xff'),
])
def test_keeps_existing_bytes_and_adds_after_them(tmp_path, content, expected):
    path = tmp_path / 'log.jsonl'
    path.write_bytes(b'first\n')
    append(path, content)
    assert path.read_bytes() == expected


def test_adds_no_separator_after_a_partial_last_line(tmp_path):
    path = tmp_path / 'log.jsonl'
    path.write_bytes(b'{"torn":')
    append(path, '1}\n')
    assert path.read_bytes() == b'{"torn":1}\n'


def test_successive_appends_land_in_order(tmp_path):
    path = tmp_path / 'log.jsonl'
    for index in range(50):
        append(path, f'{index}\n')
    assert path.read_text().splitlines() == [str(index) for index in range(50)]


def test_mixes_text_and_bytes(tmp_path):
    path = tmp_path / 'log.jsonl'
    append(path, 'text\n')
    append(path, b'bytes\n')
    append(path, 'text\n')
    assert path.read_bytes() == b'text\nbytes\ntext\n'


@pytest.mark.parametrize('content', ['', b''])
def test_empty_content_creates_an_empty_file_and_leaves_an_existing_one(tmp_path, content):
    created = tmp_path / 'new.jsonl'
    append(created, content)
    assert created.read_bytes() == b''
    existing = tmp_path / 'old.jsonl'
    existing.write_bytes(b'kept\n')
    append(existing, content)
    assert existing.read_bytes() == b'kept\n'


def test_writes_into_the_same_inode(tmp_path):
    path = tmp_path / 'log.jsonl'
    path.write_bytes(b'first\n')
    inode = path.stat().st_ino
    append(path, 'second\n')
    assert path.stat().st_ino == inode


def test_an_open_reader_sees_the_appended_bytes(tmp_path):
    path = tmp_path / 'log.jsonl'
    path.write_bytes(b'first\n')
    with path.open('rb') as reader:
        assert reader.readline() == b'first\n'
        append(path, 'second\n')
        assert reader.readline() == b'second\n'


def test_leaves_no_other_files(tmp_path):
    path = tmp_path / 'logs' / 'log.jsonl'
    path.parent.mkdir()
    append(path, 'one\n')
    append(path, 'two\n')
    assert sorted(p.name for p in path.parent.iterdir()) == ['log.jsonl']


def test_preserves_the_mode_of_an_existing_file(tmp_path):
    path = tmp_path / 'log.jsonl'
    path.write_bytes(b'first\n')
    path.chmod(0o600)
    append(path, 'second\n')
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_syncs_a_new_file_after_writing_then_its_directory(tmp_path):
    path = tmp_path / 'log.jsonl'
    synced = []

    def fsync(fd):
        metadata = os.fstat(fd)
        if stat.S_ISREG(metadata.st_mode):
            assert metadata.st_ino == path.stat().st_ino
            assert path.read_bytes() == b'line\n'
            synced.append('file')
        else:
            assert stat.S_ISDIR(metadata.st_mode)
            assert metadata.st_ino == tmp_path.stat().st_ino
            synced.append('directory')

    with patch('os.fsync', side_effect=fsync):
        append(path, 'line\n')
    assert synced == ['file', 'directory']


def test_syncs_only_the_file_when_it_already_exists(tmp_path):
    path = tmp_path / 'log.jsonl'
    path.write_bytes(b'first\n')
    synced = []

    def fsync(fd):
        metadata = os.fstat(fd)
        assert stat.S_ISREG(metadata.st_mode)
        assert path.read_bytes() == b'first\nsecond\n'
        synced.append('file')

    with patch('os.fsync', side_effect=fsync):
        append(path, 'second\n')
    assert synced == ['file']


def test_a_failed_sync_propagates(tmp_path):
    path = tmp_path / 'log.jsonl'
    with patch('os.fsync', side_effect=OSError('disk gone')), pytest.raises(OSError, match='disk gone'):
        append(path, 'line\n')


def test_rejects_a_directory_path(tmp_path):
    with pytest.raises(IsADirectoryError):
        append(tmp_path, 'line\n')
