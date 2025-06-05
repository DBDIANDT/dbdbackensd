# custom_storages.py
"""
Custom Storage Backend pour Django utilisant l'API native Backblaze B2
Version corrigée avec gestion des clés API B2
"""
import os
import io
import json
import base64
import hashlib
import mimetypes
import threading
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.utils.encoding import force_bytes


@deconstructible
class MediaStorage(Storage):
    """
    Storage backend utilisant l'API native Backblaze B2
    Compatible avec votre configuration existante
    """
    
    def __init__(self):
        # Utilisation de vos variables d'environnement existantes
        self.key_id = settings.AWS_ACCESS_KEY_ID
        self.app_key = settings.AWS_SECRET_ACCESS_KEY
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.region_name = settings.AWS_S3_REGION_NAME
        self.location = settings.AWS_LOCATION  # 'media'
        
        # Cache pour l'authentification
        self._auth_cache = {}
        self._auth_lock = threading.Lock()
        self._upload_url_cache = {}
        self._upload_url_lock = threading.Lock()
        
        # Configuration depuis vos settings
        self.file_overwrite = settings.AWS_S3_FILE_OVERWRITE
        self.querystring_auth = settings.AWS_QUERYSTRING_AUTH
        self.default_acl = settings.AWS_DEFAULT_ACL
        
        # Mode debug (désactivé en production)
        self.debug = getattr(settings, 'B2_DEBUG', False)
        
    def _log(self, message):
        """Log en mode debug uniquement"""
        if self.debug:
            print(f"[B2 Storage] {message}")
    
    def _normalize_name(self, name):
        """Normalise le nom du fichier avec le préfixe location"""
        if self.location:
            name = f"{self.location}/{name}"
        return name.replace('\\', '/').lstrip('/')
    
    def _get_auth_data(self):
        """Obtient ou rafraîchit l'authentification B2"""
        with self._auth_lock:
            # Vérifier le cache
            if 'auth_data' in self._auth_cache:
                auth_data = self._auth_cache['auth_data']
                expires_at = self._auth_cache.get('expires_at')
                if expires_at and datetime.now() < expires_at:
                    return auth_data
            
            # Nouvelle authentification
            auth_url = 'https://api.backblazeb2.com/b2api/v2/b2_authorize_account'
            credentials = f"{self.key_id}:{self.app_key}"
            encoded = base64.b64encode(credentials.encode()).decode()
            
            headers = {'Authorization': f'Basic {encoded}'}
            response = requests.get(auth_url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"B2 auth failed: {response.text}")
            
            auth_data = response.json()
            
            # Mettre en cache (expire dans 23 heures)
            self._auth_cache['auth_data'] = auth_data
            self._auth_cache['expires_at'] = datetime.now() + timedelta(hours=23)
            
            return auth_data
    
    def _get_bucket_id(self):
        """Récupère l'ID du bucket"""
        auth_data = self._get_auth_data()
        
        url = f"{auth_data['apiUrl']}/b2api/v2/b2_list_buckets"
        headers = {'Authorization': auth_data['authorizationToken']}
        data = {
            'accountId': auth_data['accountId'],
            'bucketName': self.bucket_name
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            raise Exception(f"Failed to list buckets: {response.text}")
        
        buckets = response.json()['buckets']
        for bucket in buckets:
            if bucket['bucketName'] == self.bucket_name:
                return bucket['bucketId']
        
        raise Exception(f"Bucket {self.bucket_name} not found")
    
    def _get_upload_url(self):
        """Obtient une URL d'upload (avec cache)"""
        with self._upload_url_lock:
            # Vérifier le cache
            if 'upload_data' in self._upload_url_cache:
                upload_data = self._upload_url_cache['upload_data']
                expires_at = self._upload_url_cache.get('expires_at')
                if expires_at and datetime.now() < expires_at:
                    return upload_data
            
            # Nouvelle URL d'upload
            auth_data = self._get_auth_data()
            bucket_id = self._get_bucket_id()
            
            url = f"{auth_data['apiUrl']}/b2api/v2/b2_get_upload_url"
            headers = {'Authorization': auth_data['authorizationToken']}
            data = {'bucketId': bucket_id}
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code != 200:
                raise Exception(f"Failed to get upload URL: {response.text}")
            
            upload_data = response.json()
            
            # Mettre en cache (expire dans 23 heures)
            self._upload_url_cache['upload_data'] = upload_data
            self._upload_url_cache['expires_at'] = datetime.now() + timedelta(hours=23)
            
            return upload_data
    
    def _save(self, name, content):
        """Sauvegarde un fichier sur B2"""
        # Normaliser le nom avec le préfixe location
        name = self._normalize_name(name)
        
        # Préparer le contenu
        content.seek(0)
        file_data = content.read()
        
        # Calculer SHA1
        sha1 = hashlib.sha1(file_data).hexdigest()
        
        # Déterminer le content type
        content_type = getattr(content, 'content_type', None)
        if not content_type:
            content_type, _ = mimetypes.guess_type(name)
            if not content_type:
                content_type = 'application/octet-stream'
        
        # Obtenir URL d'upload
        upload_data = self._get_upload_url()
        
        # Headers pour l'upload
        headers = {
            'Authorization': upload_data['authorizationToken'],
            'X-Bz-File-Name': quote(name),
            'Content-Type': content_type,
            'X-Bz-Content-Sha1': sha1,
            'Content-Length': str(len(file_data))
        }
        
        # Upload
        response = requests.post(
            upload_data['uploadUrl'],
            headers=headers,
            data=file_data
        )
        
        if response.status_code != 200:
            # Réinitialiser le cache en cas d'erreur
            self._upload_url_cache.clear()
            raise Exception(f"Upload failed: {response.text}")
        
        result = response.json()
        
        # Retourner le nom sans le préfixe location pour Django
        return_name = result['fileName']
        if self.location and return_name.startswith(self.location + '/'):
            return_name = return_name[len(self.location) + 1:]
        
        return return_name
    
    def _open(self, name, mode='rb'):
        """Ouvre un fichier depuis B2"""
        if 'w' in mode:
            raise ValueError("Writing to B2 files not supported via open()")
        
        name = self._normalize_name(name)
        auth_data = self._get_auth_data()
        
        # Construire l'URL de téléchargement
        download_url = f"{auth_data['downloadUrl']}/file/{self.bucket_name}/{quote(name)}"
        
        # Télécharger le fichier
        headers = {'Authorization': auth_data['authorizationToken']}
        response = requests.get(download_url, headers=headers, stream=True)
        
        if response.status_code == 404:
            raise FileNotFoundError(f"File {name} not found")
        elif response.status_code != 200:
            raise Exception(f"Download failed: {response.text}")
        
        # Retourner comme ContentFile
        return ContentFile(response.content, name=name)
    
    def delete(self, name):
        """Supprime un fichier de B2"""
        name = self._normalize_name(name)
        auth_data = self._get_auth_data()
        
        # D'abord, obtenir les infos du fichier
        file_info = self._get_file_info(name)
        if not file_info:
            return  # Fichier n'existe pas
        
        # Supprimer le fichier
        url = f"{auth_data['apiUrl']}/b2api/v2/b2_delete_file_version"
        headers = {'Authorization': auth_data['authorizationToken']}
        data = {
            'fileId': file_info['fileId'],
            'fileName': name
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            raise Exception(f"Delete failed: {response.text}")
    
    def exists(self, name):
        """Vérifie si un fichier existe"""
        name = self._normalize_name(name)
        return self._get_file_info(name) is not None
    
    def _get_file_info(self, name):
        """Obtient les informations d'un fichier"""
        auth_data = self._get_auth_data()
        bucket_id = self._get_bucket_id()
        
        url = f"{auth_data['apiUrl']}/b2api/v2/b2_list_file_names"
        headers = {'Authorization': auth_data['authorizationToken']}
        data = {
            'bucketId': bucket_id,
            'prefix': name,
            'maxFileCount': 1
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            raise Exception(f"List files failed: {response.text}")
        
        files = response.json()['files']
        for file in files:
            if file['fileName'] == name:
                # Log pour debug
                self._log(f"File info: {json.dumps(file, indent=2)}")
                return file
        
        return None
    
    def size(self, name):
        """Retourne la taille d'un fichier"""
        name = self._normalize_name(name)
        file_info = self._get_file_info(name)
        if not file_info:
            raise FileNotFoundError(f"File {name} not found")
        
        # B2 utilise 'contentLength' au lieu de 'size'
        return file_info.get('contentLength', file_info.get('size', 0))
    
    def url(self, name):
        """Retourne l'URL publique d'un fichier"""
        name = self._normalize_name(name)
        
        # Si querystring_auth est False, utiliser l'URL publique
        if not self.querystring_auth:
            # Utiliser le custom domain configuré
            if hasattr(settings, 'AWS_S3_CUSTOM_DOMAIN'):
                return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{quote(name)}"
            else:
                auth_data = self._get_auth_data()
                return f"{auth_data['downloadUrl']}/file/{self.bucket_name}/{quote(name)}"
        
        # Sinon, générer une URL présignée
        auth_data = self._get_auth_data()
        bucket_id = self._get_bucket_id()
        
        file_info = self._get_file_info(name)
        if not file_info:
            raise FileNotFoundError(f"File {name} not found")
        
        # Générer un token de téléchargement
        url = f"{auth_data['apiUrl']}/b2api/v2/b2_get_download_authorization"
        headers = {'Authorization': auth_data['authorizationToken']}
        data = {
            'bucketId': bucket_id,
            'fileNamePrefix': name,
            'validDurationInSeconds': 3600  # 1 heure
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get download authorization: {response.text}")
        
        download_auth = response.json()
        
        # Construire l'URL présignée
        return f"{auth_data['downloadUrl']}/file/{self.bucket_name}/{quote(name)}?Authorization={download_auth['authorizationToken']}"
    
    def get_available_name(self, name, max_length=None):
        """Retourne un nom de fichier disponible"""
        if self.file_overwrite:
            return name
        return super().get_available_name(name, max_length)
    
    def listdir(self, path):
        """Liste les fichiers dans un répertoire"""
        if path:
            path = self._normalize_name(path)
        
        auth_data = self._get_auth_data()
        bucket_id = self._get_bucket_id()
        
        if not path.endswith('/') and path:
            path += '/'
        
        url = f"{auth_data['apiUrl']}/b2api/v2/b2_list_file_names"
        headers = {'Authorization': auth_data['authorizationToken']}
        
        files = []
        dirs = set()
        start_filename = None
        
        while True:
            data = {
                'bucketId': bucket_id,
                'prefix': path,
                'maxFileCount': 1000,
                'delimiter': '/'
            }
            
            if start_filename:
                data['startFileName'] = start_filename
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code != 200:
                raise Exception(f"List files failed: {response.text}")
            
            result = response.json()
            self._log(f"Listdir result: {json.dumps(result, indent=2)}")
            
            # Fichiers
            for file in result.get('files', []):
                filename = file['fileName']
                if filename.startswith(path):
                    relative_path = filename[len(path):]
                    if '/' not in relative_path:
                        files.append(relative_path)
            
            # Répertoires (préfixes communs)
            for prefix in result.get('commonPrefixes', []):
                if prefix.startswith(path):
                    dir_name = prefix[len(path):].rstrip('/')
                    dirs.add(dir_name)
            
            # Pagination
            if result.get('nextFileName'):
                start_filename = result['nextFileName']
            else:
                break
        
        return list(dirs), files
    
    def get_modified_time(self, name):
        """Retourne la date de modification d'un fichier"""
        name = self._normalize_name(name)
        file_info = self._get_file_info(name)
        if not file_info:
            raise FileNotFoundError(f"File {name} not found")
        
        # B2 retourne le timestamp en millisecondes
        timestamp = file_info['uploadTimestamp'] / 1000
        return datetime.fromtimestamp(timestamp)
    
    def get_created_time(self, name):
        """Retourne la date de création (même que modification pour B2)"""
        return self.get_modified_time(name)