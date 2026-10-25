# guard/tests/test_check_files.py
import os, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_files

class Check(unittest.TestCase):
    def test_blocked_extension_fails(self):
        self.assertTrue(check_files.problems([("data/export.csv", 10)], allow=[]))

    def test_allowlisted_pattern_passes(self):
        self.assertEqual(check_files.problems([("results/passk.csv", 10)], allow=["results/*.csv"]), [])

    def test_large_file_fails(self):
        self.assertTrue(check_files.problems([("model.bin", 60 * 1024 * 1024)], allow=[]))

    def test_large_file_cannot_be_allowlisted(self):
        self.assertTrue(check_files.problems([("results/big.csv", 60 * 1024 * 1024)], allow=["results/*.csv"]))

    def test_ordinary_code_passes(self):
        self.assertEqual(check_files.problems([("src/app.py", 2000), ("README.md", 900)], allow=[]), [])


class ChangedFiles(unittest.TestCase):
    """Runs changed_files against a real throwaway git repository."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        previous = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, previous)
        self.git("init", "-q")

    def git(self, *args):
        cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def names(self, rev_range):
        return sorted(name for name, _ in check_files.changed_files(rev_range))

    def test_added_file_is_reported(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        Path("new.csv").write_text("a,b")
        self.commit("second")
        self.assertEqual(self.names("HEAD~1..HEAD"), ["new.csv"])

    def test_rename_into_blocked_name_is_reported(self):
        Path("plain.txt").write_text("a,b")
        self.commit("first")
        self.git("mv", "plain.txt", "moved.csv")
        self.commit("second")
        self.assertEqual(self.names("HEAD~1..HEAD"), ["moved.csv"])

    def test_non_ascii_name_is_reported(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        Path("Übersicht.csv").write_text("a,b")
        self.commit("second")
        self.assertEqual(self.names("HEAD~1..HEAD"), ["Übersicht.csv"])

    def test_empty_tree_range_includes_the_root_commit(self):
        Path("first.csv").write_text("a,b")
        self.commit("first")
        empty_tree = self.git("hash-object", "-t", "tree", os.devnull)
        self.assertEqual(self.names(f"{empty_tree}..HEAD"), ["first.csv"])

if __name__ == "__main__":
    unittest.main()
