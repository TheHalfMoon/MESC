"""Transport-level tests for MRL-0801 public Hugging Face metadata."""
from __future__ import annotations

import urllib.error
from email.message import Message
from io import BytesIO
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject

REV = "842da3794eaa0b77d5f08bae87a17459d91ff475"
PATH = "model-00001-of-00002.safetensors"
ETAG = "a" * 64


class Response:
    def __init__(self, status: int, headers: Message, url: str, body: bytes = b"") -> None:
        self.status = status
        self.headers = headers
        self._url = url
        self._body = BytesIO(body)

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, size: int) -> bytes:
        return self._body.read(size)


class Opener:
    def __init__(self, sequence: list[object]) -> None:
        self.sequence = sequence
        self.urls: list[str] = []

    def open(self, request: object, timeout: float) -> Response:
        del timeout
        self.urls.append(request.full_url)  # type: ignore[attr-defined]
        value = self.sequence.pop(0)
        if isinstance(value, BaseException):
            raise value
        assert isinstance(value, Response)
        return value


def headers(**values: str) -> Message:
    result = Message()
    for key, value in values.items():
        result[key.replace("_", "-")] = value
    return result


def redirect(url: str, values: Message) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, 307, "redirect", values, None)


def transport_with(opener: Opener) -> subject.UrllibHfPublicTransport:
    transport = subject.UrllibHfPublicTransport()
    transport._metadata_opener = opener  # type: ignore[attr-defined]
    return transport


def test_internal_redirect_preserves_query_and_final_metadata() -> None:
    first = "https://huggingface.co/google/gemma/resolve/" + REV + "/" + PATH
    location = "/api/resolve-cache/models/google/gemma/" + REV + "/file?etag=abc%2Fdef"
    opener = Opener(
        [
            redirect(first, headers(Location=location)),
            Response(
                200,
                headers(X_Repo_Commit=REV, Content_Length="4", ETag=ETAG),
                "https://huggingface.co/final",
            ),
        ]
    )
    item = transport_with(opener).metadata(model_id="google/gemma", revision=REV, path=PATH)
    assert "?etag=abc%2Fdef" in opener.urls[1]
    assert item.commit_sha == REV
    assert item.byte_count == 4
    assert item.etag == ETAG


def test_external_redirect_never_uses_redirect_content_length_as_target_size() -> None:
    url = "https://huggingface.co/google/gemma/resolve/" + REV + "/" + PATH
    bad = headers(Location="https://cdn-lfs.huggingface.co/file", Content_Length="37")
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="authoritative linked metadata"):
        transport_with(Opener([redirect(url, bad)])).metadata(
            model_id="google/gemma", revision=REV, path=PATH
        )


def test_external_redirect_requires_and_uses_linked_identity() -> None:
    url = "https://huggingface.co/google/gemma/resolve/" + REV + "/" + PATH
    linked = headers(
        Location="https://cdn-lfs.huggingface.co/file?signature=secret",
        X_Repo_Commit=REV,
        X_Linked_Size="123",
        X_Linked_Etag=ETAG,
        Content_Length="37",
    )
    item = transport_with(Opener([redirect(url, linked)])).metadata(
        model_id="google/gemma", revision=REV, path=PATH
    )
    assert item.byte_count == 123
    assert item.etag == ETAG
    assert item.location.startswith("https://cdn-lfs.huggingface.co/")


def test_public_access_failure_has_no_credential_fallback() -> None:
    url = "https://huggingface.co/google/gemma/resolve/" + REV + "/" + PATH
    forbidden = urllib.error.HTTPError(url, 403, "forbidden", Message(), None)
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="public unauthenticated"):
        transport_with(Opener([forbidden])).metadata(
            model_id="google/gemma",
            revision=REV,
            path=PATH,
        )


def test_byte_stream_rejects_unsafe_final_redirect() -> None:
    item = subject.HfRemoteFileMetadata(PATH, REV, 4, ETAG, "https://huggingface.co/file")
    transport = subject.UrllibHfPublicTransport()
    transport._download_opener = Opener(  # type: ignore[attr-defined]
        [Response(200, headers(Content_Length="4"), "https://127.0.0.1/file", b"data")]
    )
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="non-global"):
        list(transport.iter_bytes(metadata=item))
