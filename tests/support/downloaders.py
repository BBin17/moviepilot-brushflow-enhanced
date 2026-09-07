"""Deterministic downloader fakes; no networking or filesystem deletion."""


class FakeQbClient:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.calls = []

    def _call(self, action, torrent_hashes):
        self.calls.append((action, torrent_hashes))
        result = self.outcomes.get(action, True)
        if isinstance(result, Exception):
            raise result
        return result

    def torrents_reannounce(self, *, torrent_hashes):
        return self._call("reannounce", torrent_hashes)

    def torrents_start(self, *, torrent_hashes):
        return self._call("start", torrent_hashes)

    def torrents_stop(self, *, torrent_hashes):
        return self._call("stop", torrent_hashes)


class FakeDownloader:
    def __init__(self, torrents=(), *, client=None, error=None):
        self.torrents = {row["hash"]: dict(row) for row in torrents}
        self.qbc = client
        self.error = error
        self.calls = []

    def get_torrents(self):
        self.calls.append(("get_torrents",))
        return list(self.torrents.values()), self.error

    def delete_torrents(self, *, ids, delete_file=False):
        # Simulates ONLY in-memory task removal. Tests must never call real qB.
        self.calls.append(("delete_torrents", tuple(ids), delete_file))
        for torrent_hash in ids:
            self.torrents.pop(torrent_hash, None)
        return True
