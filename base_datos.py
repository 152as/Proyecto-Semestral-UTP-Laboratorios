import os
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. Cargamos las variables del archivo .env que creaste
load_dotenv()

class ConexionDB:
    _instancia = None

    def __new__(cls):
        # Implementación de Singleton: Solo una conexión para toda la App
        if cls._instancia is None:
            cls._instancia = super(ConexionDB, cls).__new__(cls)
            
            # 2. Leemos las credenciales desde el entorno
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            
            try:
                # 3. Inicializamos el cliente oficial de Supabase
                # Este objeto 'cliente' es el que usaremos en la Fachada
                cls._instancia.cliente = create_client(url, key)
                cls._instancia.estado = "Conectado a Supabase"
                print(">>> [DB] Conexión exitosa a Supabase (Singleton Activo).")
            except Exception as e:
                cls._instancia.cliente = None
                cls._instancia.estado = f"Error: {e}"
                print(f">>> [DB] Fallo al conectar: {e}")
                
        return cls._instancia

    def obtener_estado(self):
        """Devuelve el estado actual de la conexión."""
        return self.estado