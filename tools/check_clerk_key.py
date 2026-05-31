from app.core.config import settings as s

k = s.clerk_secret_key
print("secret len:", len(k))
print("prefix:", k[:11])
print("suffix:", k[-4:])
print("has whitespace/quotes:", any(c in k for c in (" ", '"', "'", "\n", "\r", "\t")))
pk = s.clerk_publishable_key
print("pub prefix:", pk[:8], "pub len:", len(pk))
