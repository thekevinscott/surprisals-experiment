"""Atomic publication syncs content before rename and the directory afterward."""

import os
import stat
from unittest.mock import patch

import pytest

from surprisals_experiment.sdk.utils.write import write


@pytest.mark.parametrize('content', ['new text\n', b'new bytes\x00\xff'])
def test_write_syncs_file_before_rename_and_parent_after(tmp_path, content):
    path = tmp_path / 'artifact'
    path.write_bytes(b'old')
    expected = content.encode() if isinstance(content, str) else content
    synced = []

    def fsync(fd):
        metadata = os.fstat(fd)
        if stat.S_ISREG(metadata.st_mode):
            synced.append('file')
            temporary, = tmp_path.glob('.artifact.*')
            assert metadata.st_ino == temporary.stat().st_ino
            assert temporary.read_bytes() == expected
            assert path.read_bytes() == b'old'
        else:
            assert stat.S_ISDIR(metadata.st_mode)
            assert metadata.st_ino == tmp_path.stat().st_ino
            synced.append('directory')
            assert path.read_bytes() == expected

    with patch('os.fsync', side_effect=fsync) as sync:
        write(path, content)
    assert sync.call_count == 2
    assert synced == ['file', 'directory']
    assert path.read_bytes() == expected
    assert not list(tmp_path.glob('.artifact.*'))


@pytest.mark.parametrize('content', ['same text\n', b'same bytes\x00\xff'])
def test_write_skips_identical_content(tmp_path, content):
    path = tmp_path / 'artifact'
    write(path, content)
    inode = path.stat().st_ino
    with patch('os.fsync') as sync:
        write(path, content)
    assert sync.call_count == 0
    assert path.stat().st_ino == inode
