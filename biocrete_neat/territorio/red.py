"""Red para los recolectores de Blur: reintentos y cadena TLS completa sin desactivar la verificación."""
from __future__ import annotations

import re
import shutil
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Blur-BioCrete/1.0 (investigacion academica)"

_CONTEXTOS: dict[str, ssl.SSLContext] = {}


def _contexto_con_intermedio(host: str) -> ssl.SSLContext | None:
    """Servidores que no envían su certificado intermedio (frecuente en sitios del Estado).

    Se hace lo mismo que un navegador ("AIA fetching"): se lee la URL del emisor que trae el propio
    certificado del servidor, se descarga ese intermedio y se agrega a las CA de confianza. La
    verificación sigue activa: el intermedio solo se acepta si encadena con una raíz de confianza.
    """
    if host in _CONTEXTOS:
        return _CONTEXTOS[host]
    if not shutil.which("openssl"):
        return None
    pem = ssl.get_server_certificate((host, 443))
    texto = subprocess.run(["openssl", "x509", "-noout", "-text"], input=pem, capture_output=True, text=True).stdout
    m = re.search(r"CA Issuers - URI:(\S+)", texto)
    if not m:
        return None
    crudo = urllib.request.urlopen(urllib.request.Request(m.group(1), headers={"User-Agent": UA}), timeout=60).read()
    inter = crudo.decode() if crudo.lstrip().startswith(b"-----BEGIN") else ssl.DER_cert_to_PEM_cert(crudo)
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cadata=inter)
    _CONTEXTOS[host] = ctx
    print(f"  · {host}: cadena completada con el intermedio de {m.group(1)}")
    return ctx


def abrir(url: str, datos: bytes | None = None, intentos=3, tiempo=90):
    host = urllib.parse.urlparse(url).hostname or ""
    ctx = _CONTEXTOS.get(host) or ssl.create_default_context()
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, data=datos, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=tiempo, context=ctx) as r:
                return r.read()
        except (ssl.SSLCertVerificationError, urllib.error.URLError) as e:
            causa = getattr(e, "reason", e)
            if not isinstance(causa, ssl.SSLCertVerificationError):
                if i == intentos - 1:
                    raise
                time.sleep(5 * (i + 1))
                continue
            nuevo = _contexto_con_intermedio(host)
            if nuevo is None or nuevo is ctx:
                raise RuntimeError(f"certificado TLS inválido en {url}: {causa}") from e
            ctx = nuevo
        except Exception as e:  # noqa: BLE001
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


def bajar_archivo(url: str, destino, intentos=3, tiempo=600) -> None:
    """Descarga a disco por bloques (rásters grandes), a un archivo temporal que se renombra al terminar."""
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=tiempo) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(destino)
            return
        except urllib.error.HTTPError:
            raise
        except Exception:  # noqa: BLE001
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))
