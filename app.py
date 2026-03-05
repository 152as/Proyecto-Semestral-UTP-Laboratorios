from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from gestor_facade import GestorSistemaLabsFacade
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_utp' 
gestor = GestorSistemaLabsFacade()

@app.route('/')
def login_view():
    if 'rol' in session: return redirigir_por_rol(session['rol'])
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def procesar_login():
    correo = request.form.get('correo_institucional')
    password = request.form.get('password')
    res = gestor.iniciar_sesion(correo, password)
    if res.get("exito"):
        u = res["datos"]
        session.update({'usuario_id': u['id'], 'nombre': f"{u['nombre']} {u['apellido']}", 'rol': u['rol']})
        return redirigir_por_rol(session['rol'])
    flash(res.get("mensaje", 'Credenciales incorrectas.'), 'error')
    return redirect(url_for('login_view'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_view'))

# --- AÑADIDO: RUTA DE RECUPERACIÓN DE CONTRASEÑA ---
@app.route('/recuperar_password', methods=['POST'])
def procesar_recuperacion():
    correo = request.form.get('correo_recuperacion')
    res = gestor.recuperar_password(correo)
    if res.get("exito"):
        flash(res.get("mensaje"), "success")
    else:
        flash(res.get("mensaje"), "error")
    return redirect(url_for('login_view'))
# ---------------------------------------------------

# --- RUTA DE REGISTRO MODIFICADA (CON FLASH MESSAGES) ---
@app.route('/registro', methods=['GET', 'POST'])
def registro_view():
    if request.method == 'POST':
        # Capturamos la respuesta del Facade
        res = gestor.registrar_usuario(
            request.form.get('nombre'), 
            request.form.get('apellido'), 
            request.form.get('dni'), 
            request.form.get('correo_institucional'), 
            request.form.get('password')
        )
        
        # Validamos si fue exitoso o no
        if res.get("exito"): 
            flash("Cuenta creada exitosamente. Ahora puedes iniciar sesión.", "success")
            return redirect(url_for('login_view'))
        else:
            # Si falla (ej. por RLS o correo duplicado), mostramos el error
            flash(f"Error al registrar: {res.get('mensaje')}", "error")
            
    return render_template('registro.html')
# --------------------------------------------------------

def redirigir_por_rol(rol):
    if rol in ['Coordinador', 'Operador']: return redirect(url_for('ver_dashboard'))
    session.clear()
    return redirect(url_for('login_view'))

# --- AÑADIDO: CONEXIÓN DE LABORATORIOS Y CALENDARIO AL DASHBOARD ---
@app.route('/dashboard')
def ver_dashboard():
    if 'rol' not in session: return redirect(url_for('login_view'))
    
    # Obtenemos las métricas, los laboratorios y los eventos para FullCalendar
    metricas_db = gestor.obtener_metricas_dashboard()
    laboratorios_db = gestor.obtener_laboratorios_con_estado()
    eventos_calendario = gestor.obtener_horarios_fullcalendar()
    
    return render_template('laboratorios.html', laboratorios=laboratorios_db, metricas=metricas_db, eventos_json=eventos_calendario)
# ------------------------------------------------------

# --- INVENTARIO ---
@app.route('/inventario')
def vista_inventario():
    if 'rol' not in session: return redirect(url_for('login_view'))
    return render_template('inventario.html', equipos=gestor.obtener_inventario(), catalogos=gestor.obtener_catalogos())

@app.route('/inventario/crear', methods=['POST'])
def registrar_equipo():
    if 'rol' not in session: return redirect(url_for('login_view'))
    datos = {
        'nombre': request.form.get('nombre'), 'codigo_inventario': request.form.get('codigo_inventario'),
        'id_laboratorio': request.form.get('id_laboratorio'), 'id_tipo_equipo': request.form.get('id_tipo_equipo'),
        'id_marca': 1, 'observacion': request.form.get('ram'), 'id_estado': 1,
        'numero_serie_fabricante': request.form.get('numero_serie') or 'S/N'
    }
    gestor.registrar_equipo(datos)
    return redirect(url_for('vista_inventario'))

@app.route('/inventario/editar/<int:id>', methods=['POST'])
def editar_equipo(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    datos = {
        'nombre': request.form.get('nombre'), 'codigo_inventario': request.form.get('codigo_inventario'),
        'id_laboratorio': request.form.get('id_laboratorio'), 'id_tipo_equipo': request.form.get('id_tipo_equipo'),
        'observacion': request.form.get('ram'), 'id_estado': request.form.get('id_estado'),
        'numero_serie_fabricante': request.form.get('numero_serie') or 'S/N'
    }
    gestor.actualizar_equipo(id, datos)
    flash("Equipo actualizado.", "success")
    return redirect(url_for('vista_inventario'))

@app.route('/inventario/eliminar/<int:id>', methods=['POST'])
def eliminar_equipo(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    gestor.eliminar_equipo(id)
    return redirect(url_for('vista_inventario'))

# --- MANTENIMIENTO ---
@app.route('/mantenimiento')
def vista_mantenimiento():
    if 'rol' not in session: return redirect(url_for('login_view'))
    mants = gestor.obtener_mantenimientos(solo_activos=True)
    cats = gestor.obtener_catalogos_mantenimiento()
    return render_template('mantenimiento.html', mantenimientos=mants, catalogos=cats)

@app.route('/mantenimiento/crear', methods=['POST'])
def crear_mantenimiento():
    if 'rol' not in session: return redirect(url_for('login_view'))
    id_equipo = request.form.get('id_equipo')
    datos = {
        'id_tipo_mantenimiento': request.form.get('id_tipo_mantenimiento'),
        'id_encargado': request.form.get('id_encargado'), 
        'motivo': request.form.get('motivo'),
        'fecha_inicio': request.form.get('fecha_inicio'), 
        'fecha_finalizacion': request.form.get('fecha_finalizacion'),
        'finalizado': False
    }
    gestor.registrar_mantenimiento(datos, id_equipo)
    flash("Ticket abierto. Equipo actualizado a MANTENIMIENTO.", "success")
    return redirect(url_for('vista_mantenimiento'))

@app.route('/mantenimiento/editar/<int:id>', methods=['POST'])
def editar_mantenimiento(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    is_finalized = request.form.get('finalizado') == 'on'
    motivo = request.form.get('motivo')
    datos = {
        'id_tipo_mantenimiento': request.form.get('id_tipo_mantenimiento'),
        'id_encargado': request.form.get('id_encargado'),
        'motivo': motivo,
        'finalizado': is_finalized
    }
    if is_finalized: datos['fecha_finalizacion'] = datetime.now().isoformat()
    if gestor.actualizar_mantenimiento(id, datos):
        if is_finalized: flash(f"Mantenimiento finalizado para: {motivo}. Equipo restaurado.", "success")
        else: flash("Información del ticket actualizada.", "success")
    else: flash("No se pudo actualizar el mantenimiento. Revisa la terminal.", "error")
    return redirect(url_for('vista_mantenimiento'))

@app.route('/mantenimiento/eliminar/<int:id>', methods=['POST'])
def eliminar_mantenimiento(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    gestor.eliminar_mantenimiento(id)
    flash("Ticket eliminado y equipo restaurado.", "info")
    return redirect(url_for('vista_mantenimiento'))

# --- USUARIOS (RESTRINGIDO A COORDINADOR) ---
@app.route('/usuarios')
def vista_usuarios():
    if 'rol' not in session or session['rol'] != 'Coordinador': return redirect(url_for('ver_dashboard'))
    return render_template('usuarios.html', usuarios=gestor.obtener_usuarios())

@app.route('/usuarios/crear', methods=['POST'])
def crear_usuario():
    if 'rol' not in session or session['rol'] != 'Coordinador': return redirect(url_for('ver_dashboard'))
    datos = {
        'nombre': request.form.get('nombre'), 'apellido': request.form.get('apellido'),
        'dni': request.form.get('dni'), 'correo_institucional': request.form.get('correo_institucional'),
        'password': request.form.get('password'), 'id_rol': request.form.get('id_rol')
    }
    if gestor.crear_usuario_admin(datos): flash(f"Usuario {datos['nombre']} creado exitosamente.", "success")
    else: flash("Error al crear usuario. Revisa que el correo no exista ya.", "error")
    return redirect(url_for('vista_usuarios'))

@app.route('/usuarios/editar/<int:id>', methods=['POST'])
def editar_usuario(id):
    if 'rol' not in session or session['rol'] != 'Coordinador': return redirect(url_for('ver_dashboard'))
    datos = { 'nombre': request.form.get('nombre'), 'apellido': request.form.get('apellido'), 'dni': request.form.get('dni'), 'id_rol': int(request.form.get('id_rol')) }
    if gestor.actualizar_usuario(id, datos): flash("Datos del usuario actualizados.", "success")
    else: flash("Error al actualizar.", "error")
    return redirect(url_for('vista_usuarios'))

@app.route('/usuarios/estado/<int:id>', methods=['POST'])
def estado_usuario(id):
    if 'rol' not in session or session['rol'] != 'Coordinador': return redirect(url_for('ver_dashboard'))
    
    estado_crudo = request.form.get('estado_actual')
    nuevo_estado = not (estado_crudo == 'True')

    if gestor.cambiar_estado_usuario(id, nuevo_estado): 
        flash("Estado modificado exitosamente.", "success")
    else:
        flash("No se pudo cambiar el estado del usuario. Revisa la terminal.", "error")
        
    return redirect(url_for('vista_usuarios'))

# --- PRÉSTAMOS ---
@app.route('/prestamos')
def vista_prestamos(): 
    if 'rol' not in session: return redirect(url_for('login_view'))
    prestamos_db = gestor.obtener_prestamos()
    catalogos_prestamos = gestor.obtener_catalogos_prestamos()
    return render_template('prestamos.html', prestamos=prestamos_db, catalogos=catalogos_prestamos)

@app.route('/prestamos/crear', methods=['POST'])
def registrar_prestamo():
    if 'rol' not in session: return redirect(url_for('login_view'))
    
    equipos_seleccionados = request.form.getlist('id_equipos')
    
    datos = {
        'id_usuario': request.form.get('id_usuario'),
        'id_encargado': request.form.get('id_encargado'),
        'proposito': request.form.get('proposito'),
        'fecha_prestamo': request.form.get('fecha_prestamo'),
        'fecha_devolucion': request.form.get('fecha_devolucion'),
        'id_estado_prestamo': 1 
    }
    
    res = gestor.registrar_prestamo(datos, equipos_seleccionados)
    if res.get("exito"):
        flash(res.get("mensaje"), "success")
    else:
        flash(res.get("mensaje"), "error")
        
    return redirect(url_for('vista_prestamos'))

@app.route('/prestamos/recibir/<int:id>', methods=['POST'])
def recibir_prestamo(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    if gestor.recibir_prestamo(id):
        flash("Equipos recibidos y restaurados al inventario principal.", "success")
    else:
        flash("Error al procesar la devolución.", "error")
    return redirect(url_for('vista_prestamos'))

# --- PROGRAMACIÓN Y HORARIOS ---
@app.route('/horarios')
def vista_horarios(): 
    if 'rol' not in session: return redirect(url_for('login_view'))
    
    horarios_db = gestor.obtener_horarios()
    laboratorios_db = gestor.obtener_laboratorios_con_estado()
    catalogos = gestor.obtener_catalogos_horarios()
    
    return render_template('horarios.html', horarios=horarios_db, laboratorios=laboratorios_db, catalogos=catalogos)

@app.route('/horarios/crear', methods=['POST'])
def crear_horario():
    if 'rol' not in session: return redirect(url_for('login_view'))
    
    datos = {
        'id_usuario': request.form.get('id_usuario'),
        'id_laboratorio': request.form.get('id_laboratorio'),
        'dia_semana': int(request.form.get('dia_semana')),
        'hora_inicio': request.form.get('hora_inicio'),
        'hora_final': request.form.get('hora_final'),
        'fecha_inicio_semestre': request.form.get('fecha_inicio_semestre'),
        'fecha_final_semestre': request.form.get('fecha_final_semestre'),
        'activo': True
    }
    
    res = gestor.registrar_horario(datos)
    if res.get("exito"):
        flash(res.get("mensaje"), "success")
    else:
        flash(res.get("mensaje"), "error")
        
    return redirect(url_for('vista_horarios'))

@app.route('/horarios/editar/<int:id>', methods=['POST'])
def editar_horario(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    
    datos = {
        'id_usuario': request.form.get('id_usuario'),
        'id_laboratorio': request.form.get('id_laboratorio'),
        'dia_semana': int(request.form.get('dia_semana')),
        'hora_inicio': request.form.get('hora_inicio'),
        'hora_final': request.form.get('hora_final'),
        'fecha_inicio_semestre': request.form.get('fecha_inicio_semestre'),
        'fecha_final_semestre': request.form.get('fecha_final_semestre')
    }
    
    res = gestor.actualizar_horario(id, datos)
    if res.get("exito"):
        flash(res.get("mensaje"), "success")
    else:
        flash(res.get("mensaje"), "error")
        
    return redirect(url_for('vista_horarios'))

@app.route('/horarios/eliminar/<int:id>', methods=['POST'])
def eliminar_horario(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    if gestor.eliminar_horario(id):
        flash("La asignación del horario fue eliminada correctamente.", "info")
    else:
        flash("Error al eliminar la asignación.", "error")
    return redirect(url_for('vista_horarios'))

@app.route('/laboratorios/editar_capacidad/<int:id>', methods=['POST'])
def editar_capacidad_lab(id):
    if 'rol' not in session: return redirect(url_for('login_view'))
    nueva_capacidad = int(request.form.get('capacidad_maxima'))
    
    if gestor.actualizar_capacidad_laboratorio(id, nueva_capacidad):
        flash("Capacidad del laboratorio actualizada correctamente.", "success")
    else:
        flash("Error al actualizar la capacidad.", "error")
        
    return redirect(url_for('vista_horarios'))

# --- REPORTES ANALÍTICOS (RESTRINGIDO A COORDINADOR) ---
@app.route('/reportes')
def vista_reportes():
    if session.get('rol') != 'Coordinador': return redirect(url_for('ver_dashboard'))
    
    datos_resumen = gestor.obtener_datos_reporte()
    return render_template('reportes.html', datos=datos_resumen)

@app.route('/reportes/exportar/excel', methods=['POST'])
def exportar_excel():
    if session.get('rol') != 'Coordinador': return redirect(url_for('ver_dashboard'))
    
    modulo_seleccionado = request.form.get('modulo_exportar')
    archivo_excel = gestor.exportar_datos_excel(modulo_seleccionado)
    
    if archivo_excel:
        nombre_archivo = f"Reporte_UTP_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(
            archivo_excel, 
            as_attachment=True, 
            download_name=nombre_archivo, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        flash(f"No hay datos registrados en {modulo_seleccionado} para exportar.", "info")
        return redirect(url_for('vista_reportes'))

# AÑADIDO: RUTA PARA GENERAR PDF
@app.route('/reportes/exportar/pdf', methods=['GET'])
def exportar_pdf():
    if session.get('rol') != 'Coordinador': return redirect(url_for('ver_dashboard'))
    
    archivo_pdf = gestor.exportar_datos_pdf()
    if archivo_pdf:
        nombre_archivo = f"Reporte_Ejecutivo_UTP_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return send_file(
            archivo_pdf, 
            as_attachment=True, 
            download_name=nombre_archivo, 
            mimetype='application/pdf'
        )
    else:
        flash("Error al generar el documento PDF.", "error")
        return redirect(url_for('vista_reportes'))

if __name__ == '__main__':
    app.run(debug=True)