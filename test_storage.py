import base64
import json
import os
import tempfile
import unittest

from stoichio import storage


def github_content_record(data, sha="sha"):
    encoded = base64.b64encode((json.dumps(data) + "\n").encode("utf-8")).decode("ascii")
    return {
        "sha": sha,
        "content": encoded,
    }


class FakeGitHubJsonStore(storage.GitHubJsonStore):
    def __init__(self, data, sha="base"):
        super().__init__("owner/repo", "token", branch="lab-data")
        self.remote_data = data
        self.remote_sha = sha
        self.puts = []

    def _load_content_record(self, path, allow_404=False):
        return github_content_record(self.remote_data, self.remote_sha)

    def _request(self, method, url, payload=None, allow_404=False):
        if method != "PUT":
            raise AssertionError(f"Unexpected fake GitHub method: {method}")
        self.remote_data = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
        self.remote_sha = f"sha-{len(self.puts) + 1}"
        self.puts.append(payload)
        return {"content": {"sha": self.remote_sha}}


class FakeLargeGitHubJsonStore(storage.GitHubJsonStore):
    def __init__(self, data, sha="large-sha"):
        super().__init__("owner/repo", "token", branch="lab-data")
        self.remote_data = data
        self.remote_sha = sha
        self.gets = []

    def _request(self, method, url, payload=None, allow_404=False):
        if method != "GET":
            raise AssertionError(f"Unexpected fake GitHub method: {method}")
        self.gets.append(url)
        if "/git/blobs/" in url:
            return github_content_record(self.remote_data, self.remote_sha)
        return {
            "sha": self.remote_sha,
            "content": "",
            "encoding": "none",
            "git_url": f"https://api.github.com/repos/owner/repo/git/blobs/{self.remote_sha}",
        }


class FailingBackend:
    def save(self, path, data):
        raise RuntimeError("backend exploded")


class StorageGithubMergeTests(unittest.TestCase):
    def test_github_json_store_loads_large_content_from_blob_api(self):
        store = FakeLargeGitHubJsonStore({"items": [{"id": "large", "value": 1}]})

        data = store.load("msds_inventory.json", {})

        self.assertEqual(data, {"items": [{"id": "large", "value": 1}]})
        self.assertTrue(any("/git/blobs/" in url for url in store.gets))

    def test_github_json_store_merges_non_conflicting_dict_updates(self):
        store = FakeGitHubJsonStore({"Fe2O3": {"status": "old"}})

        local = store.load("material_densities.json", {})
        store.remote_data = {
            "Fe2O3": {"status": "old"},
            "TiO2": {"status": "checked"},
        }
        store.remote_sha = "remote"
        local["Al2O3"] = {"status": "checked"}

        store.save("material_densities.json", local)

        self.assertEqual(store.remote_data["Fe2O3"]["status"], "old")
        self.assertEqual(store.remote_data["TiO2"]["status"], "checked")
        self.assertEqual(store.remote_data["Al2O3"]["status"], "checked")

    def test_github_json_store_rejects_same_key_conflict(self):
        store = FakeGitHubJsonStore({"Fe2O3": {"status": "old"}})

        local = store.load("material_densities.json", {})
        store.remote_data = {"Fe2O3": {"status": "checked"}}
        store.remote_sha = "remote"
        local["Fe2O3"] = {"status": "preferred"}

        with self.assertRaisesRegex(RuntimeError, "Could not merge concurrent edits"):
            store.save("material_densities.json", local)

    def test_github_json_store_merges_list_appends_by_entry_id(self):
        store = FakeGitHubJsonStore([{"entry_id": "a", "value": 1}])

        local = store.load("history.json", [])
        store.remote_data = [
            {"entry_id": "a", "value": 1},
            {"entry_id": "b", "value": 2},
        ]
        store.remote_sha = "remote"
        local.append({"entry_id": "c", "value": 3})

        store.save("history.json", local)

        self.assertEqual(
            [entry["entry_id"] for entry in store.remote_data],
            ["a", "b", "c"],
        )

    def test_github_json_store_merges_different_list_deletions_by_entry_id(self):
        store = FakeGitHubJsonStore([
            {"entry_id": "a", "value": 1},
            {"entry_id": "b", "value": 2},
        ])

        local = store.load("history.json", [])
        store.remote_data = [{"entry_id": "a", "value": 1}]
        store.remote_sha = "remote"
        local = [entry for entry in local if entry["entry_id"] != "a"]

        store.save("history.json", local)

        self.assertEqual(store.remote_data, [])


class StorageFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_backend = storage._storage_backend
        self.old_label = storage._storage_label
        self.old_error = storage._storage_error
        self.old_vercel = os.environ.get("VERCEL")

    def tearDown(self):
        storage._storage_backend = self.old_backend
        storage._storage_label = self.old_label
        storage._storage_error = self.old_error
        if self.old_vercel is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = self.old_vercel
        self.tempdir.cleanup()

    def test_save_json_does_not_fallback_to_local_on_vercel_write_failure(self):
        path = os.path.join(self.tempdir.name, "history.json")
        os.environ["VERCEL"] = "1"
        storage._storage_backend = FailingBackend()

        with self.assertRaisesRegex(RuntimeError, "data was not saved"):
            storage.save_json(path, [{"entry_id": "new"}])

        self.assertFalse(os.path.exists(path))
        self.assertIsInstance(storage._storage_backend, FailingBackend)
        self.assertIn("backend exploded", storage.storage_error())

    def test_save_json_still_falls_back_to_local_outside_vercel(self):
        path = os.path.join(self.tempdir.name, "history.json")
        os.environ.pop("VERCEL", None)
        storage._storage_backend = FailingBackend()

        storage.save_json(path, [{"entry_id": "new"}])

        self.assertEqual(storage.load_json_file(path, []), [{"entry_id": "new"}])
        self.assertIsNone(storage._storage_backend)
        self.assertIn("backend exploded", storage.storage_error())


if __name__ == "__main__":
    unittest.main()
