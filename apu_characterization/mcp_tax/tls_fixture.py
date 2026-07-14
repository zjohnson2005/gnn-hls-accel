"""Runtime-only local CA and localhost certificate fixture for MCP-01."""

from __future__ import annotations

import hashlib
import os
import shutil
import ssl
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class TlsFixtureUnavailable(RuntimeError):
    """The host cannot generate the local, CA-verified TLS fixture."""


def _inside_git_worktree(path: Path) -> bool:
    candidate = path.resolve()
    return any((parent / ".git").exists() for parent in (candidate, *candidate.parents))


def _run_openssl(openssl: str, args: list[str], *, cwd: Path) -> None:
    try:
        subprocess.run(
            [openssl, *args],
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise TlsFixtureUnavailable(f"OpenSSL certificate generation failed: {detail}") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TlsFixtureUnavailable(f"OpenSSL certificate generation failed: {exc}") from exc


@dataclass
class TlsFixture:
    """One ephemeral CA/server certificate set shared by a matrix run."""

    directory: Path
    ca_cert_path: Path
    server_cert_path: Path
    server_key_path: Path
    ca_sha256: str
    server_fingerprint_sha256: str
    _temporary_directory: tempfile.TemporaryDirectory[str]

    @classmethod
    def create(
        cls,
        *,
        matrix_id: str = "matrix",
        parent: str | os.PathLike[str] | None = None,
        openssl_executable: str | None = None,
    ) -> "TlsFixture":
        """Generate a runtime certificate set outside a Git worktree."""
        openssl = openssl_executable or shutil.which("openssl")
        if not openssl:
            raise TlsFixtureUnavailable("OpenSSL executable is not available")
        safe_id = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in matrix_id
        )[:48]
        temp = tempfile.TemporaryDirectory(
            prefix=f"mcp-tax-tls-{safe_id}-",
            dir=os.fspath(parent) if parent is not None else None,
        )
        directory = Path(temp.name)
        if _inside_git_worktree(directory):
            temp.cleanup()
            raise ValueError("TLS fixtures must be generated outside a Git worktree")

        ca_key = directory / "ca-key.pem"
        ca_cert = directory / "ca-cert.pem"
        server_key = directory / "server-key.pem"
        server_csr = directory / "server.csr"
        server_cert = directory / "server-cert.pem"
        extensions = directory / "server-extensions.cnf"
        extensions.write_text(
            "[v3_server]\n"
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
            "subjectAltName=@alt_names\n"
            "[alt_names]\n"
            "DNS.1=localhost\n"
            "IP.1=127.0.0.1\n"
            "IP.2=::1\n",
            encoding="ascii",
        )
        try:
            _run_openssl(
                openssl,
                [
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-sha256",
                    "-days",
                    "2",
                    "-subj",
                    "/CN=MCP Tax Local Test CA",
                    "-addext",
                    "basicConstraints=critical,CA:TRUE,pathlen:0",
                    "-addext",
                    "keyUsage=critical,keyCertSign,cRLSign",
                    "-addext",
                    "subjectKeyIdentifier=hash",
                    "-keyout",
                    os.fspath(ca_key),
                    "-out",
                    os.fspath(ca_cert),
                ],
                cwd=directory,
            )
            _run_openssl(
                openssl,
                [
                    "req",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-sha256",
                    "-subj",
                    "/CN=localhost",
                    "-keyout",
                    os.fspath(server_key),
                    "-out",
                    os.fspath(server_csr),
                ],
                cwd=directory,
            )
            _run_openssl(
                openssl,
                [
                    "x509",
                    "-req",
                    "-sha256",
                    "-days",
                    "2",
                    "-in",
                    os.fspath(server_csr),
                    "-CA",
                    os.fspath(ca_cert),
                    "-CAkey",
                    os.fspath(ca_key),
                    "-CAcreateserial",
                    "-extfile",
                    os.fspath(extensions),
                    "-extensions",
                    "v3_server",
                    "-out",
                    os.fspath(server_cert),
                ],
                cwd=directory,
            )
            try:
                os.chmod(ca_key, 0o600)
                os.chmod(server_key, 0o600)
            except OSError:
                pass

            ca_bytes = ca_cert.read_bytes()
            cert_pem = server_cert.read_text(encoding="ascii")
            cert_der = ssl.PEM_cert_to_DER_cert(cert_pem)
            return cls(
                directory=directory,
                ca_cert_path=ca_cert,
                server_cert_path=server_cert,
                server_key_path=server_key,
                ca_sha256=hashlib.sha256(ca_bytes).hexdigest(),
                server_fingerprint_sha256=hashlib.sha256(cert_der).hexdigest(),
                _temporary_directory=temp,
            )
        except Exception:
            temp.cleanup()
            raise

    def client_context(self) -> ssl.SSLContext:
        """Return a client context that trusts only this fixture CA."""
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=os.fspath(self.ca_cert_path),
        )
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context

    def server_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            certfile=os.fspath(self.server_cert_path),
            keyfile=os.fspath(self.server_key_path),
        )
        return context

    def public_metadata(self) -> dict[str, str]:
        """Return publishable certificate identity without private-key material."""
        return {
            "ca_sha256": self.ca_sha256,
            "server_fingerprint_sha256": self.server_fingerprint_sha256,
        }

    def close(self) -> None:
        self._temporary_directory.cleanup()

    def __enter__(self) -> "TlsFixture":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

