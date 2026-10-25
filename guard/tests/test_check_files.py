# guard/tests/test_check_files.py
import contextlib, io, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
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

    def test_every_data_and_document_extension_fails(self):
        extensions = (".csv .tsv .parquet .xlsx .xls .zip .7z .tar .tgz .gz .sql .dump .sqlite .db .pem .key .p8 .p12 .pfx"
                      " .dwg .dxf .step .stp .pdf .doc .docx .pptx .xlsm .xlsb .ods .jsonl .ndjson .pkl .npy .h5 .feather"
                      " .avro .mdb .bak").split()
        for extension in extensions:
            with self.subTest(extension=extension):
                self.assertTrue(check_files.problems([(f"data/export{extension}", 10)], allow=[]))

    def test_matching_ignores_case(self):
        for path in ("DATA.CSV", "exports/Report.PDF", "cad/Part.StEp"):
            with self.subTest(path=path):
                self.assertTrue(check_files.problems([(path, 10)], allow=[]))

    def test_plain_json_passes(self):
        self.assertEqual(check_files.problems([("package.json", 300), ("tests/fixtures/sample.json", 900)], allow=[]), [])

    def test_env_templates_pass(self):
        for path in (".env.example", ".env.sample", ".env.template", "app/.env.example"):
            with self.subTest(path=path):
                self.assertEqual(check_files.problems([(path, 10)], allow=[]), [])

    def test_env_files_fail(self):
        for path in (".env", ".env.local", ".env.production", ".envrc", "config/.env", "prod.env", ".ENV"):
            with self.subTest(path=path):
                self.assertTrue(check_files.problems([(path, 10)], allow=[]))


class Allowlist(unittest.TestCase):
    def read(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "guard-allow.txt"
            path.write_text(text)
            return check_files.read_allowlist(str(path))

    def test_comments_blank_lines_and_indented_comments_are_ignored(self):
        text = "# header\n\n  # indented comment\n\tresults/*.csv  \n   \ndocs/*.pdf\n"
        self.assertEqual(self.read(text), ["results/*.csv", "docs/*.pdf"])

    def test_missing_file_means_empty_allowlist(self):
        self.assertEqual(check_files.read_allowlist("/nonexistent/guard-allow.txt"), [])


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

    def test_empty_tree_range_includes_files_deleted_later(self):
        Path("first.csv").write_text("a,b")
        self.commit("first")
        self.git("rm", "-q", "first.csv")
        self.commit("second")
        empty_tree = self.git("hash-object", "-t", "tree", os.devnull)
        self.assertEqual(self.names(f"{empty_tree}..HEAD"), ["first.csv"])

    def test_file_added_and_deleted_within_one_push_is_reported(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        Path("secret.csv").write_text("a,b")
        self.commit("add")
        self.git("rm", "-q", "secret.csv")
        self.commit("delete")
        self.assertEqual(self.names("HEAD~2..HEAD"), ["secret.csv"])

    def test_file_large_in_one_commit_and_shrunk_in_the_next_is_rejected(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        Path("blob.bin").write_text("x" * 2000)
        self.commit("grow")
        Path("blob.bin").write_text("x")
        self.commit("shrink")
        with mock.patch.object(check_files, "MAX_BYTES", 1000):
            found = check_files.problems(check_files.changed_files("HEAD~2..HEAD"), allow=[])
        self.assertEqual(len(found), 1)
        self.assertIn("blob.bin", found[0])

    def test_data_file_on_a_merged_side_branch_is_reported(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        self.git("checkout", "-q", "-b", "side")
        Path("side.csv").write_text("a,b")
        self.commit("side")
        self.git("checkout", "-q", "-")
        Path("main.txt").write_text("y")
        self.commit("main")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "side")
        self.assertEqual(self.names("HEAD~2..HEAD"), ["main.txt", "side.csv"])

    def test_submodule_pointer_is_skipped(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        self.git("update-index", "--add", "--cacheinfo", "160000," + "1" * 40 + ",vendor.csv")
        self.git("commit", "-q", "-m", "submodule")
        self.assertEqual(self.names("HEAD~1..HEAD"), [])

    def test_file_changed_in_two_commits_is_reported_once(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        Path("data.csv").write_text("a,b")
        self.commit("add")
        Path("data.csv").write_text("a,b,c")
        self.commit("change")
        found = check_files.problems(check_files.changed_files("HEAD~2..HEAD"), allow=[])
        self.assertEqual(len(found), 1)

    def test_git_error_fails_closed_and_prints_the_message(self):
        Path("keep.txt").write_text("x")
        self.commit("first")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["check_files.py", "no-such-ref..HEAD"]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check_files.main()
        self.assertEqual(code, 1)
        self.assertIn("no-such-ref", err.getvalue())

if __name__ == "__main__":
    unittest.main()
