# custom_storage.py
from django.core.files.storage import Storage
from supabase import create_client
import os
import io

class SupabaseStorage(Storage):
    def __init__(self):
        self.supabase = create_client(
            os.environ.get('SUPABASE_URL'), 
            os.environ.get('SUPABASE_KEY')
        )
        self.bucket_name = 'media'  # Assurez-vous que ce bucket existe

    def _save(self, name, content):
        # Convertir le contenu en bytes
        file_bytes = content.read()
        
        # Upload sur Supabase
        self.supabase.storage.from_(self.bucket_name).upload(
            file=file_bytes, 
            path=name, 
            file_options={"content-type": content.content_type}
        )
        return name

    def exists(self, name):
        try:
            # Vérifier si le fichier existe
            self.supabase.storage.from_(self.bucket_name).get(name)
            return True
        except:
            return False

    def url(self, name):
        # Générer l'URL publique du fichier
        return self.supabase.storage.from_(self.bucket_name).get_public_url(name)