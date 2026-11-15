"""Build a CA bundle = certifi + the Windows certificate store, for networks with SSL inspection.

The ESPHome / ESP-IDF downloaders use certifi, which does not contain the company's proxy
root certificate. Windows does, so both are combined into one PEM file.

Usage:  .\\.venv\\Scripts\\python.exe tools\\make_ca_bundle.py
Then point REQUESTS_CA_BUNDLE and SSL_CERT_FILE at the printed file (see README).
"""

import ssl
from pathlib import Path

import certifi

out = Path.home() / ".certs" / "ca-bundle.pem"
out.parent.mkdir(exist_ok=True)

pems = [Path(certifi.where()).read_text(encoding="ascii")]
seen = set()
for store in ("ROOT", "CA"):
    for der, encoding, trust in ssl.enum_certificates(store):
        if encoding == "x509_asn" and der not in seen:
            seen.add(der)
            pems.append(ssl.DER_cert_to_PEM_cert(der))

out.write_text("\n".join(pems), encoding="ascii")
print(f"{len(seen)} Windows certificates + certifi written to {out}")
