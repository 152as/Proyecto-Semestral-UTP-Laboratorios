from base_datos import ConexionDB
from datetime import datetime, date, timedelta
import pandas as pd
from io import BytesIO

# AÑADIDO: LIBRERÍAS PARA PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors

class GestorSistemaLabsFacade:
    
    def __init__(self):
        self.db = ConexionDB()

    # --- MÉTODOS DE AUTENTICACIÓN Y USUARIOS ---

    def iniciar_sesion(self, correo_institucional, password):
        try:
            print(f"Intentando login en Supabase para: {correo_institucional}")
            auth_response = self.db.cliente.auth.sign_in_with_password({
                "email": correo_institucional,
                "password": password
            })
            user_data = self.db.cliente.table('usuarios') \
                .select('id, nombre, apellido, id_rol, activo') \
                .eq('correo_institucional', correo_institucional) \
                .execute()

            if user_data.data:
                usuario_db = user_data.data[0]
                
                if not usuario_db.get('activo', True):
                    return {"exito": False, "mensaje": "Tu cuenta ha sido deshabilitada. Contacta al Coordinador."}

                id_rol = usuario_db.get('id_rol')
                nombre_rol = 'Coordinador' if id_rol == 1 else 'Operador' if id_rol == 2 else 'Desconocido'

                return {
                    "exito": True, 
                    "mensaje": "Bienvenido",
                    "datos": {
                        "id": usuario_db['id'],
                        "nombre": usuario_db['nombre'],
                        "apellido": usuario_db['apellido'],
                        "rol": nombre_rol 
                    }
                }
            return {"exito": False, "mensaje": "Usuario no encontrado."}
        except Exception as e:
            print(f"Error en login: {e}")
            return {"exito": False, "mensaje": "Credenciales inválidas."}

    def registrar_usuario(self, nombre, apellido, dni, correo_institucional, password):
        try:
            # --- AÑADIDO: VALIDACIONES PREVIAS (PRE-FLIGHT CHECKS) ---
            # 1. Validar longitud de la contraseña
            if len(password) < 6:
                return {"exito": False, "mensaje": "La contraseña debe tener al menos 6 caracteres."}
                
            # 2. Validar si la cédula ya existe en la BD
            check_dni = self.db.cliente.table('usuarios').select('dni').eq('dni', dni).execute()
            if check_dni.data and len(check_dni.data) > 0:
                return {"exito": False, "mensaje": "Esta cédula ya se encuentra registrada en el sistema."}
                
            # 3. Validar si el correo ya existe en la BD
            check_correo = self.db.cliente.table('usuarios').select('correo_institucional').eq('correo_institucional', correo_institucional).execute()
            if check_correo.data and len(check_correo.data) > 0:
                return {"exito": False, "mensaje": "Este correo institucional ya está en uso."}
            # ---------------------------------------------------------

            auth_response = self.db.cliente.auth.sign_up({"email": correo_institucional, "password": password})
            nuevo_usuario = {
                "nombre": nombre, "apellido": apellido, "dni": dni,
                "correo_institucional": correo_institucional, "id_rol": 1,
                "activo": True
            }
            self.db.cliente.table('usuarios').insert(nuevo_usuario).execute()
            return {"exito": True, "mensaje": "Usuario registrado."}
        except Exception as e:
            mensaje_error = str(e)
            if 'usuarios_dni_key' in mensaje_error or '23505' in mensaje_error:
                return {"exito": False, "mensaje": "Esta cédula ya se encuentra registrada en el sistema."}
            elif 'User already registered' in mensaje_error or 'correo_institucional_key' in mensaje_error:
                return {"exito": False, "mensaje": "Este correo institucional ya está en uso."}
            return {"exito": False, "mensaje": "Revisa los datos ingresados o intenta más tarde."}

    # --- AÑADIDO: RECUPERACIÓN DE CONTRASEÑA ---
    def recuperar_password(self, correo):
        try:
            # Supabase enviará un correo con el token temporal de recuperación
            res = self.db.cliente.auth.reset_password_for_email(correo)
            return {"exito": True, "mensaje": "Se ha enviado un enlace de recuperación a tu correo institucional."}
        except Exception as e:
            print(f"Error al recuperar contraseña: {e}")
            return {"exito": False, "mensaje": "No se pudo procesar la solicitud. Verifica que el correo esté registrado."}
    # -------------------------------------------

    # --- MÉTODOS CRUD DE USUARIOS ---
    
    def obtener_usuarios(self):
        try:
            response = self.db.cliente.table('usuarios').select('*, roles(nombre)').order('id').execute()
            if response.data:
                lista_usuarios = []
                for u in response.data:
                    rol_nombre = u.get("roles", {}).get("nombre", "Desconocido") if u.get("roles") else "Desconocido"
                    if rol_nombre == "Desconocido":
                        rol_nombre = 'Coordinador' if u.get('id_rol') == 1 else 'Operador' if u.get('id_rol') == 2 else 'Desconocido'

                    lista_usuarios.append({
                        "id": u['id'],
                        "nombre": u.get('nombre', ''),
                        "apellido": u.get('apellido', ''),
                        "nombre_completo": f"{u.get('nombre', '')} {u.get('apellido', '')}",
                        "dni": u['dni'],
                        "correo": u['correo_institucional'],
                        "id_rol": u.get('id_rol', 2),
                        "rol": rol_nombre,
                        "activo": u.get('activo', True) 
                    })
                return lista_usuarios
            return []
        except Exception as e:
            print(f"Error al obtener usuarios: {e}")
            return []

    def crear_usuario_admin(self, datos):
        try:
            # --- VALIDACIONES PREVIAS PARA ADMIN ---
            if len(datos['password']) < 6:
                return False
                
            check_dni = self.db.cliente.table('usuarios').select('dni').eq('dni', datos['dni']).execute()
            if check_dni.data and len(check_dni.data) > 0:
                return False
                
            check_correo = self.db.cliente.table('usuarios').select('correo_institucional').eq('correo_institucional', datos['correo_institucional']).execute()
            if check_correo.data and len(check_correo.data) > 0:
                return False
            # ------------------------------------------------

            auth_response = self.db.cliente.auth.sign_up({
                "email": datos['correo_institucional'], 
                "password": datos['password']
            })
            nuevo_usuario = {
                "nombre": datos['nombre'],
                "apellido": datos['apellido'],
                "dni": datos['dni'],
                "correo_institucional": datos['correo_institucional'],
                "id_rol": int(datos['id_rol']),
                "activo": True
            }
            res_user = self.db.cliente.table('usuarios').insert(nuevo_usuario).execute()
            
            # Si el usuario es Operador (Rol 2), lo asignamos como encargado
            if res_user.data and int(datos['id_rol']) == 2:
                id_nuevo_usuario = res_user.data[0]['id']
                
                # FIX INTELIGENTE: Buscamos un ID de laboratorio que SÍ exista en la BD
                lab_query = self.db.cliente.table('laboratorios').select('id').limit(1).execute()
                id_lab_real = lab_query.data[0]['id'] if lab_query.data else None
                
                if id_lab_real:
                    self.db.cliente.table('encargados').insert({
                        "id_usuario": id_nuevo_usuario,
                        "id_laboratorio": id_lab_real, 
                        "activo": True
                    }).execute()
                
            return True
        except Exception as e:
            print(f"Error en crear_usuario_admin: {e}")
            return False

    def actualizar_usuario(self, id_usuario, datos):
        try:
            self.db.cliente.table('usuarios').update(datos).eq('id', id_usuario).execute()
            return True
        except Exception as e:
            return False

    def cambiar_estado_usuario(self, id_usuario, nuevo_estado):
        print(f"\n[DEBUG FACADE] -> Entrando a cambiar_estado_usuario(id={id_usuario}, estado={nuevo_estado})")
        try:
            res_user = self.db.cliente.table('usuarios').update({'activo': nuevo_estado}).eq('id', id_usuario).execute()
            print(f"[DEBUG FACADE] -> Respuesta Supabase (usuarios): {res_user}")
            try:
                res_enc = self.db.cliente.table('encargados').update({'activo': nuevo_estado}).eq('id_usuario', id_usuario).execute()
                print(f"[DEBUG FACADE] -> Respuesta Supabase (encargados): {res_enc}")
            except Exception as enc_err:
                print(f"[DEBUG FACADE] -> Advertencia: El usuario no es encargado o hubo error: {enc_err}")

            return True
        except Exception as e:
            print(f"[DEBUG FACADE] -> ❌ ERROR FATAL AL ACTUALIZAR SUPABASE: {e}")
            return False

    # --- MÉTODOS DE INVENTARIO ---

    def obtener_inventario(self):
        try:
            response = self.db.cliente.table('equipos').select(
                'id, codigo_inventario, nombre, numero_serie_fabricante, observacion, id_estado, id_laboratorio, id_tipo_equipo, laboratorios(nombre), tipos_equipo(nombre)'
            ).execute()
            if response.data:
                inventario_real = []
                for item in response.data:
                    estado_map = {1: "Operativo", 2: "Mantenimiento", 3: "Prestado"}
                    icono_map = {"Laptop": "fas fa-laptop", "Router": "fas fa-network-wired", "Monitor": "fas fa-tv"}
                    
                    nombre_tipo = item.get("tipos_equipo", {}).get("nombre", "Otro") if item.get("tipos_equipo") else "Otro"
                    
                    inventario_real.append({
                        "db_id": item.get("id"), 
                        "id": item.get("codigo_inventario"),
                        "equipo": item.get("nombre"),
                        "numero_serie": item.get("numero_serie_fabricante"), 
                        "id_tipo_equipo": item.get("id_tipo_equipo"),
                        "id_laboratorio": item.get("id_laboratorio"),
                        "id_estado": item.get("id_estado", 1),
                        "laboratorio": item.get("laboratorios", {}).get("nombre", "N/A") if item.get("laboratorios") else "N/A",
                        "estado": estado_map.get(item.get("id_estado", 1), "Operativo"),
                        "ram": item.get("observacion", "N/A"),
                        "tipo": nombre_tipo,
                        "icono": icono_map.get(nombre_tipo, "fas fa-box")
                    })
                return inventario_real
            return []
        except Exception as e:
            return []

    def obtener_catalogos(self):
        try:
            labs = self.db.cliente.table('laboratorios').select('id, nombre').execute().data
            tipos = self.db.cliente.table('tipos_equipo').select('id, nombre').execute().data
            return {'laboratorios': labs, 'tipos': tipos}
        except:
            return {'laboratorios': [], 'tipos': []}

    def registrar_equipo(self, datos):
        try:
            self.db.cliente.table('equipos').insert(datos).execute()
            return True
        except: return False
            
    def actualizar_equipo(self, id_equipo, datos):
        try:
            self.db.cliente.table('equipos').update(datos).eq('id', id_equipo).execute()
            return True
        except: return False

    def eliminar_equipo(self, id_equipo):
        try:
            self.db.cliente.table('equipos').delete().eq('id', id_equipo).execute()
            return True
        except: return False

    # --- MÉTODOS DE MANTENIMIENTO TÉCNICO ---

    def obtener_mantenimientos(self, solo_activos=False):
        try:
            query = self.db.cliente.table('mantenimientos').select(
                '*, tipos_mantenimiento(nombre), mantenimiento_equipos(id_equipo, equipos(nombre, codigo_inventario)), encargados(id_usuario, usuarios(nombre, apellido))'
            )
            if solo_activos: query = query.eq('finalizado', False)
            response = query.order('fecha_creacion', desc=True).execute()

            if response.data:
                tickets = []
                for item in response.data:
                    relacion = item.get("mantenimiento_equipos", [])
                    nombre_equipo = "Equipo Desconocido"
                    if relacion and len(relacion) > 0:
                        eq_data = relacion[0].get("equipos")
                        if eq_data: nombre_equipo = f"{eq_data.get('codigo_inventario', '')} - {eq_data.get('nombre', '')}"

                    datos_encargado = item.get("encargados")
                    nombre_operador = f"Operador #{item.get('id_encargado')}"
                    if datos_encargado and datos_encargado.get("usuarios"):
                        user_info = datos_encargado["usuarios"]
                        nombre_operador = f"{user_info.get('nombre', '')} {user_info.get('apellido', '')}"

                    tickets.append({
                        "db_id": item['id'],
                        "id": f"TKT-{item['id']}",
                        "equipo_nombre": nombre_equipo,
                        "motivo": item.get("motivo"), 
                        "tipo": item.get("tipos_mantenimiento", {}).get("nombre", "N/A") if item.get("tipos_mantenimiento") else "N/A",
                        "id_tipo": item.get("id_tipo_mantenimiento"),
                        "fecha": item.get("fecha_inicio", "").split("T")[0] if item.get("fecha_inicio") else "",
                        "fecha_fin": item.get("fecha_finalizacion", "").split("T")[0] if item.get("fecha_finalizacion") else "",
                        "encargado_id": item.get("id_encargado"),
                        "encargado_nombre": nombre_operador,
                        "finalizado": item.get("finalizado"),
                        "estado": "Finalizado" if item.get("finalizado") else "En Proceso"
                    })
                return tickets
            return []
        except Exception as e:
            return []

    def obtener_catalogos_mantenimiento(self):
        try:
            tipos = self.db.cliente.table('tipos_mantenimiento').select('id, nombre').execute().data
            encargados_raw = self.db.cliente.table('encargados').select('id, id_usuario, id_laboratorio, usuarios(nombre, apellido)').eq('activo', True).execute().data
            encargados_formateados = []
            if encargados_raw:
                for enc in encargados_raw:
                    nombre = "Desconocido"
                    if enc.get("usuarios"): nombre = f"{enc['usuarios'].get('nombre', '')} {enc['usuarios'].get('apellido', '')}"
                    encargados_formateados.append({"id": enc["id"], "nombre_completo": nombre})
            equipos = self.db.cliente.table('equipos').select('id, codigo_inventario, nombre').execute().data
            return {'tipos_mantenimiento': tipos or [], 'encargados': encargados_formateados or [], 'equipos': equipos or []}
        except Exception as e: 
            return {'tipos_mantenimiento': [], 'encargados': [], 'equipos': []}

    def registrar_mantenimiento(self, datos_mant, id_equipo):
        try:
            if 'id_equipo' in datos_mant:
                del datos_mant['id_equipo']

            inicio = datos_mant.get('fecha_inicio')
            fin = datos_mant.get('fecha_finalizacion')
            
            if not fin: 
                datos_mant['fecha_finalizacion'] = f"{inicio} 23:59:59"
            elif inicio == fin: 
                datos_mant['fecha_finalizacion'] = f"{fin} 23:59:59"

            res_mant = self.db.cliente.table('mantenimientos').insert(datos_mant).execute()
            
            if res_mant.data:
                nuevo_id_mant = res_mant.data[0]['id']
                self.db.cliente.table('mantenimiento_equipos').insert({
                    "id_mantenimiento": nuevo_id_mant, 
                    "id_equipo": int(id_equipo), 
                    "observacion": "Asignado vía web"
                }).execute()
                self.db.cliente.table('equipos').update({"id_estado": 2}).eq('id', int(id_equipo)).execute()
                return True
            return False
        except Exception as e: 
            print(f"Error crítico en registrar_mantenimiento: {e}")
            return False

    def actualizar_mantenimiento(self, id_mant, datos):
        try:
            res = self.db.cliente.table('mantenimientos').update(datos).eq('id', id_mant).execute()
            if res.data and datos.get('finalizado') == True:
                rel = self.db.cliente.table('mantenimiento_equipos').select('id_equipo').eq('id_mantenimiento', id_mant).execute()
                if rel.data:
                    id_eq = rel.data[0]['id_equipo']
                    self.db.cliente.table('equipos').update({"id_estado": 1}).eq('id', id_eq).execute()
            return True
        except: return False

    def eliminar_mantenimiento(self, id_mant):
        try:
            rel = self.db.cliente.table('mantenimiento_equipos').select('id_equipo').eq('id_mantenimiento', id_mant).execute()
            if rel.data: self.db.cliente.table('equipos').update({"id_estado": 1}).eq('id', rel.data[0]['id_equipo']).execute()
            self.db.cliente.table('mantenimiento_equipos').delete().eq('id_mantenimiento', id_mant).execute()
            self.db.cliente.table('mantenimientos').delete().eq('id', id_mant).execute()
            return True
        except: return False

    # --- MÉTRICAS DEL DASHBOARD (REALES) ---
    def obtener_metricas_dashboard(self):
        metricas = { "total_equipos": 0, "prestamos_activos": 0, "mantenimientos_pendientes": 0, "reportes_hoy": 0 }
        try:
            res_equipos = self.db.cliente.table('equipos').select('id', count='exact').execute()
            if hasattr(res_equipos, 'count'): metricas["total_equipos"] = res_equipos.count

            res_mantenimiento = self.db.cliente.table('equipos').select('id', count='exact').eq('id_estado', 2).execute()
            if hasattr(res_mantenimiento, 'count'): metricas["mantenimientos_pendientes"] = res_mantenimiento.count

            hoy = date.today().isoformat()
            res_tickets = self.db.cliente.table('mantenimientos').select('id', count='exact').gte('fecha_creacion', f"{hoy}T00:00:00").execute()
            if hasattr(res_tickets, 'count'): metricas["reportes_hoy"] = res_tickets.count
            
            res_prestamos = self.db.cliente.table('prestamos').select('id', count='exact').eq('id_estado_prestamo', 1).execute()
            if hasattr(res_prestamos, 'count'): metricas["prestamos_activos"] = res_prestamos.count
            
            return metricas
        except Exception as e:
            return metricas

    # --- MÓDULO DE PRÉSTAMOS ---
    
    def obtener_catalogos_prestamos(self):
        try:
            usuarios = self.db.cliente.table('usuarios').select('id, nombre, apellido, dni').eq('activo', True).execute().data
            enc_raw = self.db.cliente.table('usuarios').select('id, nombre, apellido').eq('activo', True).execute().data
            encargados = [{"id": e['id'], "nombre_completo": f"{e['nombre']} {e['apellido']}"} for e in enc_raw]
            equipos = self.db.cliente.table('equipos').select('id, codigo_inventario, nombre').eq('id_estado', 1).execute().data
            return {'usuarios': usuarios or [], 'encargados': encargados or [], 'equipos': equipos or []}
        except Exception as e:
            return {'usuarios': [], 'encargados': [], 'equipos': []}

    def obtener_prestamos(self):
        try:
            query = self.db.cliente.table('prestamos').select(
                '*, usuarios!prestamos_id_usuario_fkey(nombre, apellido), estados_prestamo(nombre), prestamos_detalles(equipos(codigo_inventario, nombre))'
            ).order('fecha_creacion', desc=True).execute()

            if query.data:
                lista_prestamos = []
                now = datetime.now()

                for p in query.data:
                    u_data = p.get('usuarios', {})
                    nombre_responsable = f"{u_data.get('nombre', '')} {u_data.get('apellido', '')}" if u_data else "Desconocido"

                    detalles = p.get('prestamos_detalles', [])
                    nombres_equipos = []
                    for d in detalles:
                        if d.get('equipos'): nombres_equipos.append(d['equipos']['codigo_inventario'])
                    equipos_str = ", ".join(nombres_equipos) if nombres_equipos else "Sin equipos"

                    estado_str = p.get('estados_prestamo', {}).get('nombre', 'Desconocido') if p.get('estados_prestamo') else 'Desconocido'
                    
                    atrasado = False
                    fecha_fin_raw = p.get("fecha_devolucion")
                    if fecha_fin_raw and p.get("id_estado_prestamo") == 1:
                        fin_dt = datetime.fromisoformat(fecha_fin_raw.split('+')[0]) 
                        if now > fin_dt:
                            atrasado = True
                            estado_str = "ATRASADO"

                    lista_prestamos.append({
                        "db_id": p['id'],
                        "id": f"PRS-{p['id']}",
                        "equipo": equipos_str,
                        "usuario": nombre_responsable,
                        "fecha_inicio": p.get("fecha_prestamo", "").replace("T", " ")[:16] if p.get("fecha_prestamo") else "",
                        "fecha_fin": p.get("fecha_devolucion", "").replace("T", " ")[:16] if p.get("fecha_devolucion") else "",
                        "estado": estado_str,
                        "id_estado": p.get("id_estado_prestamo"),
                        "atrasado": atrasado 
                    })
                return lista_prestamos
            return []
        except Exception as e:
            print(f"Error en obtener_prestamos: {e}")
            return []

    def registrar_prestamo(self, datos_prestamo, lista_ids_equipos):
        try:
            inicio = datetime.fromisoformat(datos_prestamo['fecha_prestamo'])
            fin = datetime.fromisoformat(datos_prestamo['fecha_devolucion'])
            if fin <= inicio: return {"exito": False, "mensaje": "La fecha de devolución es incorrecta."}

            ahora = datetime.now().isoformat()
            morosos = self.db.cliente.table('prestamos') \
                .select('id') \
                .eq('id_usuario', datos_prestamo['id_usuario']) \
                .eq('id_estado_prestamo', 1) \
                .lt('fecha_devolucion', ahora) \
                .execute()
            
            if morosos.data and len(morosos.data) > 0:
                return {"exito": False, "mensaje": "El usuario tiene préstamos vencidos. No puede solicitar más equipos hasta entregarlos."}

            for eq_id in lista_ids_equipos:
                eq_db = self.db.cliente.table('equipos').select('id_estado').eq('id', eq_id).execute()
                if eq_db.data and eq_db.data[0]['id_estado'] != 1:
                    return {"exito": False, "mensaje": f"Uno de los equipos seleccionados ya no está disponible."}

            res_prestamo = self.db.cliente.table('prestamos').insert(datos_prestamo).execute()
            
            if res_prestamo.data:
                id_nuevo_prestamo = res_prestamo.data[0]['id']
                
                for id_eq in lista_ids_equipos:
                    self.db.cliente.table('prestamos_detalles').insert({
                        "id_prestamo": id_nuevo_prestamo, "id_equipo": int(id_eq), "devolucion_pendiente": True
                    }).execute()
                    self.db.cliente.table('equipos').update({"id_estado": 3}).eq('id', int(id_eq)).execute()
                
                return {"exito": True, "mensaje": "Préstamo registrado. Equipos marcados como NO DISPONIBLES."}
            return {"exito": False, "mensaje": "Error de conexión."}
        except Exception as e:
            print(f"Error al registrar prestamo: {e}")
            return {"exito": False, "mensaje": str(e)}

    def recibir_prestamo(self, id_prestamo):
        try:
            self.db.cliente.table('prestamos').update({"id_estado_prestamo": 2}).eq('id', id_prestamo).execute()
            detalles = self.db.cliente.table('prestamos_detalles').select('id_equipo').eq('id_prestamo', id_prestamo).execute()
            
            if detalles.data:
                for d in detalles.data:
                    id_eq = d['id_equipo']
                    self.db.cliente.table('prestamos_detalles').update({"devolucion_pendiente": False}).eq('id_prestamo', id_prestamo).eq('id_equipo', id_eq).execute()
                    self.db.cliente.table('equipos').update({"id_estado": 1}).eq('id', id_eq).execute()
            return True
        except Exception as e:
            return False

    # --- MÓDULO DE HORARIOS Y LABORATORIOS ---
    
    def obtener_laboratorios_con_estado(self):
        try:
            labs = self.db.cliente.table('laboratorios').select('*').execute().data
            resultado = []
            
            now = datetime.now()
            current_day = now.isoweekday() 
            current_time = now.strftime('%H:%M:%S')
            
            if labs:
                for lab in labs:
                    pc_count_query = self.db.cliente.table('equipos').select('id', count='exact').eq('id_laboratorio', lab['id']).eq('id_estado', 1).execute()
                    pc_count = getattr(pc_count_query, 'count', 0)
                    
                    clase_actual = self.db.cliente.table('horarios_planificados')\
                        .select('id')\
                        .eq('id_laboratorio', lab['id'])\
                        .eq('dia_semana', current_day)\
                        .eq('activo', True)\
                        .lte('hora_inicio', current_time)\
                        .gte('hora_final', current_time)\
                        .execute()
                        
                    if pc_count == 0:
                        estado_lab = "Sin Registro"
                    elif clase_actual.data and len(clase_actual.data) > 0:
                        estado_lab = "En Clase"
                    else:
                        estado_lab = "Disponible"
                        
                    enc_data = self.db.cliente.table('encargados').select('usuarios(nombre, apellido)').eq('id_laboratorio', lab['id']).eq('activo', True).execute().data
                    encargado_nombre = "Sin Asignar"
                    if enc_data and enc_data[0].get('usuarios'):
                        encargado_nombre = f"{enc_data[0]['usuarios'].get('nombre', '')} {enc_data[0]['usuarios'].get('apellido', '')}"
                    
                    resultado.append({
                        "id": lab['id'],
                        "nombre": lab['nombre'],
                        "estado": estado_lab,
                        "pc_operativas": pc_count,
                        "capacidad_maxima": lab.get('capacidad_maxima', 20),
                        "encargado": encargado_nombre
                    })
            return resultado
        except Exception as e:
            print(f"Error en obtener_laboratorios_con_estado: {e}")
            return []

    def obtener_horarios(self):
        try:
            query = self.db.cliente.table('horarios_planificados').select(
                '*, laboratorios(nombre), usuarios(nombre, apellido)'
            ).eq('activo', True).order('dia_semana').execute()
            
            dias_map = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"}
            
            if query.data:
                lista = []
                for h in query.data:
                    u = h.get('usuarios', {})
                    l = h.get('laboratorios', {})
                    lista.append({
                        "id": h['id'],
                        "dia": dias_map.get(h.get('dia_semana'), "Día Desconocido"),
                        "dia_num": h.get('dia_semana'), 
                        "hora_inicio": h.get('hora_inicio', "")[:5],
                        "hora_final": h.get('hora_final', "")[:5],
                        "fecha_ini": h.get('fecha_inicio_semestre', ""), 
                        "fecha_fin": h.get('fecha_final_semestre', ""), 
                        "id_usuario": h.get('id_usuario'), 
                        "id_laboratorio": h.get('id_laboratorio'), 
                        "laboratorio": l.get('nombre', 'Laboratorio Desconocido'),
                        "usuario": f"{u.get('nombre', '')} {u.get('apellido', '')}",
                        "estado": "Confirmado"
                    })
                return lista
            return []
        except Exception as e:
            print(f"Error en obtener_horarios: {e}")
            return []

    # --- CONVERSOR DE DATOS PARA FULLCALENDAR JS ---
    def obtener_horarios_fullcalendar(self):
        try:
            horarios_crudos = self.obtener_horarios()
            eventos = []
            
            hoy = date.today()
            lunes_actual = hoy - timedelta(days=hoy.weekday())
            
            color_map = {
                "Lunes": "#3b82f6", "Martes": "#10b981", "Miércoles": "#f59e0b", 
                "Jueves": "#8b5cf6", "Viernes": "#ef4444", "Sábado": "#64748b", "Domingo": "#64748b"
            }
            
            for h in horarios_crudos:
                dias_sumar = int(h['dia_num']) - 1 
                fecha_evento = lunes_actual + timedelta(days=dias_sumar)
                
                inicio_iso = f"{fecha_evento.isoformat()}T{h['hora_inicio']}:00"
                final_iso = f"{fecha_evento.isoformat()}T{h['hora_final']}:00"
                
                eventos.append({
                    "id": h['id'],
                    "title": f"{h['usuario']}",
                    "start": inicio_iso,
                    "end": final_iso,
                    "backgroundColor": color_map.get(h['dia'], "#3b82f6"),
                    "borderColor": "transparent",
                    "extendedProps": {
                        "laboratorio": h['laboratorio'],
                        "id_laboratorio": h['id_laboratorio']
                    }
                })
            return eventos
        except Exception as e:
            print(f"Error en obtener_horarios_fullcalendar: {e}")
            return []
    # --------------------------------------------------------

    def obtener_catalogos_horarios(self):
        try:
            usuarios = self.db.cliente.table('usuarios').select('id, nombre, apellido').eq('activo', True).execute().data
            laboratorios = self.db.cliente.table('laboratorios').select('id, nombre').execute().data
            return {'usuarios': usuarios or [], 'laboratorios': laboratorios or []}
        except: 
            return {'usuarios': [], 'laboratorios': []}

    def registrar_horario(self, datos):
        try:
            if datos['hora_final'] <= datos['hora_inicio']:
                return {"exito": False, "mensaje": "Error: La hora final no puede ser menor o igual a la hora de inicio."}
            
            choques = self.db.cliente.table('horarios_planificados').select('hora_inicio, hora_final')\
                .eq('id_laboratorio', datos['id_laboratorio'])\
                .eq('dia_semana', datos['dia_semana'])\
                .eq('activo', True)\
                .execute()
            
            if choques.data:
                def parse_time(t_str):
                    return datetime.strptime(t_str[:5], '%H:%M').time()
                
                h_inicio_nuevo = parse_time(datos['hora_inicio'])
                h_final_nuevo = parse_time(datos['hora_final'])
                
                for c in choques.data:
                    h_inicio_existente = parse_time(c['hora_inicio'])
                    h_final_existente = parse_time(c['hora_final'])
                    
                    if h_inicio_nuevo < h_final_existente and h_final_nuevo > h_inicio_existente:
                        return {"exito": False, "mensaje": f"❌ CHOQUE DETECTADO: El laboratorio ya está ocupado de {c['hora_inicio'][:5]} a {c['hora_final'][:5]}."}
            
            self.db.cliente.table('horarios_planificados').insert(datos).execute()
            return {"exito": True, "mensaje": "Horario asignado exitosamente y sin choques."}
        except Exception as e:
            print(f"Error al registrar horario: {e}")
            return {"exito": False, "mensaje": "Hubo un error de conexión con la base de datos."}

    def actualizar_horario(self, id_h, datos):
        try:
            if datos['hora_final'] <= datos['hora_inicio']:
                return {"exito": False, "mensaje": "Error: La hora final no puede ser menor o igual a la hora de inicio."}
            
            choques = self.db.cliente.table('horarios_planificados').select('id, hora_inicio, hora_final')\
                .eq('id_laboratorio', datos['id_laboratorio'])\
                .eq('dia_semana', datos['dia_semana'])\
                .eq('activo', True)\
                .neq('id', id_h)\
                .execute()
            
            if choques.data:
                def parse_time(t_str):
                    return datetime.strptime(t_str[:5], '%H:%M').time()
                
                h_inicio_nuevo = parse_time(datos['hora_inicio'])
                h_final_nuevo = parse_time(datos['hora_final'])
                
                for c in choques.data:
                    h_inicio_existente = parse_time(c['hora_inicio'])
                    h_final_existente = parse_time(c['hora_final'])
                    
                    if h_inicio_nuevo < h_final_existente and h_final_nuevo > h_inicio_existente:
                        return {"exito": False, "mensaje": f"❌ CHOQUE DETECTADO: El laboratorio ya está ocupado de {c['hora_inicio'][:5]} a {c['hora_final'][:5]}."}
            
            self.db.cliente.table('horarios_planificados').update(datos).eq('id', id_h).execute()
            return {"exito": True, "mensaje": "Horario actualizado exitosamente y sin choques."}
        except Exception as e:
            print(f"Error al actualizar horario: {e}")
            return {"exito": False, "mensaje": "Hubo un error al actualizar el horario."}

    def eliminar_horario(self, id_h):
        try:
            self.db.cliente.table('horarios_planificados').update({'activo': False}).eq('id', id_h).execute()
            return True
        except Exception as e:
            print(f"Error al eliminar horario: {e}")
            return False

    def actualizar_capacidad_laboratorio(self, id_lab, nueva_capacidad):
        try:
            self.db.cliente.table('laboratorios').update({'capacidad_maxima': nueva_capacidad}).eq('id', id_lab).execute()
            return True
        except Exception as e:
            print(f"Error al actualizar capacidad: {e}")
            return False

    def obtener_laboratorios(self): return []

    # --- MÓDULO DE REPORTES ANALÍTICOS ---
    
    def obtener_datos_reporte(self):
        datos = {"tickets_abiertos": 0, "tickets_resueltos": 0, "tasa_ocupacion": "0%"}
        try:
            res_abiertos = self.db.cliente.table('mantenimientos').select('id', count='exact').eq('finalizado', False).execute()
            if hasattr(res_abiertos, 'count'): datos["tickets_abiertos"] = res_abiertos.count
            
            res_resueltos = self.db.cliente.table('mantenimientos').select('id', count='exact').eq('finalizado', True).execute()
            if hasattr(res_resueltos, 'count'): datos["tickets_resueltos"] = res_resueltos.count
            
            res_horarios = self.db.cliente.table('horarios_planificados').select('id', count='exact').eq('activo', True).execute()
            total_clases = res_horarios.count if hasattr(res_horarios, 'count') else 0
            if total_clases > 0:
                ocupacion = min(100, int((total_clases / 20) * 100)) 
                datos["tasa_ocupacion"] = f"{ocupacion}%"
                
            return datos
        except Exception as e:
            print(f"Error en estadísticas de reporte: {e}")
            return datos

    def exportar_datos_excel(self, tipo_reporte):
        try:
            output = BytesIO()
            
            if tipo_reporte == "Inventario Global de Activos":
                datos_inv = self.obtener_inventario()
                if not datos_inv: return None
                df = pd.DataFrame(datos_inv)
                columnas_mostrar = ['id', 'equipo', 'numero_serie', 'laboratorio', 'estado', 'tipo', 'ram']
                df = df[columnas_mostrar]
                df.columns = ['Código Inventario', 'Nombre Equipo', 'Número de Serie', 'Laboratorio', 'Estado Actual', 'Tipo', 'Especificaciones']
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Inventario_UTP')
                    
            elif tipo_reporte == "Historial de Préstamos (Último Mes)":
                datos_prestamos = self.obtener_prestamos()
                if not datos_prestamos: return None
                df = pd.DataFrame(datos_prestamos)
                df = df[['id', 'equipo', 'usuario', 'fecha_inicio', 'fecha_fin', 'estado']]
                df.columns = ['ID Préstamo', 'Equipos', 'Usuario Responsable', 'Fecha de Préstamo', 'Fecha de Devolución', 'Estado']
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Prestamos')

            elif tipo_reporte == "Registro de Mantenimientos (Anual)":
                datos_mant = self.obtener_mantenimientos()
                if not datos_mant: return None
                df = pd.DataFrame(datos_mant)
                df = df[['id', 'equipo_nombre', 'motivo', 'tipo', 'encargado_nombre', 'fecha', 'estado']]
                df.columns = ['ID Ticket', 'Equipo', 'Motivo del Fallo', 'Tipo de Mantenimiento', 'Técnico Asignado', 'Fecha Inicio', 'Estado']
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Mantenimientos')
                    
            elif tipo_reporte == "Asignación de Horarios por Semestre":
                datos_horarios = self.obtener_horarios()
                if not datos_horarios: return None
                df = pd.DataFrame(datos_horarios)
                df = df[['dia', 'hora_inicio', 'hora_final', 'laboratorio', 'usuario', 'estado']]
                df.columns = ['Día de la Semana', 'Hora Inicio', 'Hora Final', 'Laboratorio', 'Profesor / Encargado', 'Estado de Reserva']
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Horarios')
            else:
                return None

            output.seek(0)
            return output
            
        except Exception as e:
            print(f"Error generando Excel: {e}")
            return None

    # AÑADIDO: GENERADOR DE PDF PROFESIONAL CON REPORTLAB
    def exportar_datos_pdf(self):
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            story = []
            
            # --- DEFINICIÓN DE ESTILOS FORMALES ---
            styles = getSampleStyleSheet()
            estilo_titulo = ParagraphStyle(name='Titulo', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=10, textColor=colors.HexColor("#0f172a"))
            estilo_subtitulo = ParagraphStyle(name='Subtitulo', parent=styles['Heading2'], alignment=TA_CENTER, fontSize=12, spaceAfter=20, textColor=colors.HexColor("#3b82f6"))
            estilo_normal = styles['Normal']
            estilo_seccion = ParagraphStyle(name='Seccion', parent=styles['Heading2'], fontSize=14, spaceBefore=15, spaceAfter=10, textColor=colors.HexColor("#1e293b"))
            
            # --- ENCABEZADO INSTITUCIONAL ---
            story.append(Paragraph("<b>UNIVERSIDAD TECNOLÓGICA DE PANAMÁ</b>", estilo_titulo))
            story.append(Paragraph("<b>Centro Regional de Panamá Oeste (CRPO)</b>", estilo_subtitulo))
            story.append(Paragraph("<b>REPORTE EJECUTIVO DE OPERACIONES - LABS</b>", estilo_titulo))
            story.append(Paragraph(f"Fecha de emisión: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ParagraphStyle(name='Fecha', alignment=TA_CENTER, spaceAfter=30)))
            
            # --- SECCIÓN 1: RESUMEN GLOBAL ---
            metricas = self.obtener_metricas_dashboard()
            reportes = self.obtener_datos_reporte()
            
            story.append(Paragraph("1. RESUMEN GLOBAL DEL SISTEMA", estilo_seccion))
            datos_resumen = [
                ["Indicador Estratégico", "Valor Registrado"],
                ["Total de Equipos Físicos en Inventario", str(metricas.get("total_equipos", 0))],
                ["Préstamos de Equipos Activos Actuales", str(metricas.get("prestamos_activos", 0))],
                ["Equipos en Taller (Mantenimiento Pendiente)", str(metricas.get("mantenimientos_pendientes", 0))],
                ["Tasa de Ocupación Estudiantil de Laboratorios", str(reportes.get("tasa_ocupacion", "0%"))],
                ["Histórico de Tickets de Mantenimiento Resueltos", str(reportes.get("tickets_resueltos", 0))],
            ]
            
            tabla_resumen = Table(datos_resumen, colWidths=[350, 150])
            tabla_resumen.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#334155")),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0"))
            ]))
            story.append(tabla_resumen)
            story.append(Spacer(1, 20))
            
            # --- SECCIÓN 2: MANTENIMIENTOS CRÍTICOS ---
            story.append(Paragraph("2. MANTENIMIENTOS PENDIENTES (TICKETS ABIERTOS)", estilo_seccion))
            mants = self.obtener_mantenimientos(solo_activos=True)
            if mants:
                datos_mants = [["Ticket ID", "Equipo Afectado", "Motivo Principal", "Fecha Inicio", "Técnico Asignado"]]
                for m in mants[:10]: # Limitamos a los 10 más recientes para el reporte ejecutivo
                    datos_mants.append([m['id'], m['equipo_nombre'], m['motivo'][:30] + "...", m['fecha'], m['encargado_nombre']])
                
                tabla_mants = Table(datos_mants, colWidths=[60, 120, 130, 70, 110])
                tabla_mants.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ef4444")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0"))
                ]))
                story.append(tabla_mants)
            else:
                story.append(Paragraph("Estado óptimo: No existen tickets de mantenimiento pendientes en este momento.", estilo_normal))
                
            story.append(Spacer(1, 20))
            
            # --- SECCIÓN 3: ESTADO DE PRÉSTAMOS ---
            story.append(Paragraph("3. ÚLTIMOS PRÉSTAMOS REGISTRADOS", estilo_seccion))
            prestamos = self.obtener_prestamos()
            if prestamos:
                datos_prestamos = [["Doc ID", "Usuario Solicitante", "Equipos Asignados", "Estado Actual"]]
                for p in prestamos[:10]: # Limitamos a 10
                    datos_prestamos.append([p['id'], p['usuario'], p['equipo'][:45] + "...", p['estado']])
                    
                tabla_prestamos = Table(datos_prestamos, colWidths=[60, 150, 180, 100])
                tabla_prestamos.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#10b981")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0"))
                ]))
                story.append(tabla_prestamos)
            else:
                story.append(Paragraph("No hay registro de préstamos de equipos recientes.", estilo_normal))

            # --- CONSTRUCCIÓN FINAL DEL DOCUMENTO ---
            doc.build(story)
            buffer.seek(0)
            return buffer
        except Exception as e:
            print(f"Error generando PDF: {e}")
            return None