from cryptography.fernet import Fernet

# Générer une clé Fernet valide
key = Fernet.generate_key().decode()
print(f"Clé à mettre dans vos settings : {key}")