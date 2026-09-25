"""`jnwb.paths` names an input file exactly: where a session prefix resolves, what its bytes
hash to, and a missing path refused with the fix in the message."""

import hashlib

import pytest

from jnwb import paths


class TestSha256File:
    def test_known_vectors(self, tmp_path):
        empty, abc = tmp_path / "empty.bin", tmp_path / "abc.bin"
        empty.write_bytes(b"")
        abc.write_bytes(b"abc")
        assert paths.sha256_file(empty) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert paths.sha256_file(abc) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    @pytest.mark.parametrize("chunk_size", [1, 7, 4096, 1024 * 1024])
    def test_the_digest_does_not_depend_on_the_chunk_size(self, tmp_path, chunk_size):
        data = bytes(range(256)) * 41 + b"tail"          # 10500 bytes, not a multiple of 7
        f = tmp_path / "data.bin"
        f.write_bytes(data)
        assert paths.sha256_file(f, chunk_size=chunk_size) == hashlib.sha256(data).hexdigest()

    def test_one_changed_byte_changes_the_digest(self, tmp_path):
        a, b = tmp_path / "a.bin", tmp_path / "b.bin"
        a.write_bytes(b"\x00" * 1000)
        b.write_bytes(b"\x00" * 999 + b"\x01")
        assert paths.sha256_file(a) != paths.sha256_file(b)

    def test_a_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            paths.sha256_file(tmp_path / "absent.nwb")


class TestResolveNwbPath:
    def test_the_rec_file_wins_when_both_exist(self, tmp_path):
        (tmp_path / "s1_rec.nwb").write_bytes(b"r")
        (tmp_path / "s1.nwb").write_bytes(b"p")
        assert paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path) == tmp_path / "s1_rec.nwb"

    def test_the_plain_file_without_a_rec_file(self, tmp_path):
        (tmp_path / "s1.nwb").write_bytes(b"p")
        assert paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path) == tmp_path / "s1.nwb"

    def test_nothing_on_disk_still_names_the_plain_file(self, tmp_path):
        """Documented: only the `_rec.nwb` probe checks existence; `require` is the hard check."""
        p = paths.resolve_nwb_path("s1", nwb_dir_override=tmp_path)
        assert p == tmp_path / "s1.nwb" and not p.exists()


class TestRequire:
    def test_an_existing_path_comes_back_as_a_path(self, tmp_path):
        f = tmp_path / "x.nwb"
        f.write_bytes(b"")
        assert paths.require(str(f), "NWB file") == f

    def test_a_missing_path_names_what_and_the_env_var(self, tmp_path):
        missing = tmp_path / "nope"
        with pytest.raises(FileNotFoundError) as exc:
            paths.require(missing, "NWB session directory", env_var="JNWB_NWB_DIR")
        msg = str(exc.value)
        assert msg == f"NWB session directory not found: {missing}. Set $JNWB_NWB_DIR to point at it."

    def test_without_an_env_var_there_is_no_hint(self, tmp_path):
        missing = tmp_path / "nope"
        with pytest.raises(FileNotFoundError) as exc:
            paths.require(missing, "thing")
        assert str(exc.value) == f"thing not found: {missing}."
