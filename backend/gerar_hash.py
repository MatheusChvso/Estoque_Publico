# ficheiro: gerar_hash.py
from werkzeug.security import generate_password_hash

# A senha que você quer usar
senha_plana = "admin"

# Gera a hash usando exatamente a mesma biblioteca que a sua API usa
hash_gerada = generate_password_hash(senha_plana)

# Imprime a hash no terminal
print("A sua hash segura é:")
print(hash_gerada)