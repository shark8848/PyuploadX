"""OpenAPI completeness checks (docs 16, DoD: OpenAPI 完整)."""

from __future__ import annotations

EXPECTED_PATHS = {
    # Health / observability (16.1, 23.3)
    "/healthz",
    "/readyz",
    "/startupz",
    "/metrics",
    # Portal configuration (16.7)
    "/v1/client-config",
    # Files (16.2, 16.3)
    "/v1/files/upload",
    "/v1/files/{file_id}",
    "/v1/files/{file_id}/download",
    "/v1/files/{file_id}/presign-download",
    # Presign helpers (16.3)
    "/v1/presign/put",
    "/v1/presign/get",
    # Uploads / multipart (16.4)
    "/v1/uploads",
    "/v1/uploads/resume",
    "/v1/uploads/{upload_id}",
    "/v1/uploads/{upload_id}/parts",
    "/v1/uploads/{upload_id}/parts/presign",
    "/v1/uploads/{upload_id}/parts/{part_number}",
    "/v1/uploads/{upload_id}/parts/commit",
    "/v1/uploads/{upload_id}/refresh",
    "/v1/uploads/{upload_id}/complete",
    "/v1/uploads/{upload_id}/abort",
    # Directory uploads (16.6)
    "/v1/directory-uploads",
    "/v1/directory-uploads/{job_id}",
    "/v1/directory-uploads/{job_id}/entries",
    "/v1/directory-uploads/{job_id}/entries/stream",
    "/v1/directory-uploads/{job_id}/entries/initiate",
    "/v1/directory-uploads/{job_id}/entries/result",
    "/v1/directory-uploads/{job_id}/manifest",
    "/v1/directory-uploads/{job_id}/manifest/complete",
    "/v1/directory-uploads/{job_id}/retry",
    "/v1/directory-uploads/{job_id}/complete",
    "/v1/directory-uploads/{job_id}/cancel",
    "/v1/directory-uploads/{job_id}/lifecycle",
    # Lifecycle (16.5)
    "/v1/files/{file_id}/lifecycle",
    "/v1/files/{file_id}/lifecycle/extend",
    "/v1/files/{file_id}/lifecycle/make-permanent",
    "/v1/files/{file_id}/legal-hold",
}


def test_openapi_exposes_all_documented_endpoints(app) -> None:
    schema = app.openapi()
    actual = set(schema["paths"])
    missing = sorted(EXPECTED_PATHS - actual)
    assert not missing, f"missing documented paths: {missing}"


def test_file_upload_accepts_multipart_form_data(app) -> None:
    schema = app.openapi()
    operation = schema["paths"]["/v1/files/upload"]["post"]
    consumes = {
        content
        for content in operation.get("requestBody", {}).get("content", {})
    }
    assert "multipart/form-data" in consumes
