"""Génère les clés VAPID pour les push notifications. Lance une seule fois."""
from py_vapid import Vapid

v = Vapid()
v.generate_keys()
print("VAPID_PRIVATE_KEY=" + v.private_key.private_bytes(
    encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.PEM,
    format=__import__('cryptography.hazmat.primitives.serialization', fromlist=['PrivateFormat']).PrivateFormat.PKCS8,
    encryption_algorithm=__import__('cryptography.hazmat.primitives.serialization', fromlist=['NoEncryption']).NoEncryption(),
).decode())
print("VAPID_PUBLIC_KEY=" + v.public_key.public_bytes(
    encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.X962,
    format=__import__('cryptography.hazmat.primitives.primitives.ec', fromlist=[]).SECP256R1()
).hex())
