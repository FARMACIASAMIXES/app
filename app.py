from flask import Flask, render_template, url_for, redirect, request, flash, session
from database import config
#MySQL
from flask_mysqldb import MySQL
#
from random import sample, randint
import os
#SUBIDA DE IMG
from werkzeug.utils import secure_filename
#MAIL
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask_mail import Mail, Message
from datetime import datetime

#VARIABLE GLOBAL DE SESION, INICA SI ALGUIEN INCIÓ SESION
log = False 

app = Flask(__name__)

conexion = MySQL(app)
#UTILIZACION DEL SERVIDOR DE CORREOS
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'farmaciasamixes@gmail.com'  # EL CORREO DE LA EMPRESA
app.config['MAIL_PASSWORD'] = 'uoxg lwii gvto gnwq'   # CONTRASELA PROPORCIONADA PARA USAR EL GMAIL EMPRESARIA, ES PRIVADA Y CON PROTECCION

mail = Mail(app)


#REDIRECCION INICIAL
@app.route('/')
def index():
    
    data = {}
    data = llenar_categorias()
    mostrarP = mostrar_productos()
    numero_productos = contar_productos_carrito()
    #CARGARÁ EL HTML A MOSTRAR, Y LOS DATOS SIGUIENTES SON LOS DATOS QUE EXISTIRAN EN ESE HTML
    return render_template('cliente/inicio.html', data = data, log = log, mostrarP = mostrarP, numero_productos = numero_productos)

#AGREGA LOS PRODCUTOS AL CARRITO
@app.route('/agregar_carrito/<int:producto_id>')
def agregar_carrito(producto_id):
    print(f"Producto ID recibido: {producto_id}")  # Verificación de producto_id
    
    #INICIA EL CARRITO SI TODAVIA NO ESTÁ
    if 'carrito' not in session:
        session['carrito'] = {}
    carrito = session['carrito']
    #SE PASA A STRING MI VARIABLE
    producto_id_str = str(producto_id)  
    #SI EL MISMO PRODUCTO YA EXISTE ENTONCES QUE HAGA UN INCREMENTO
    if producto_id_str in carrito:
        carrito[producto_id_str]['cantidad'] += 1
    #EN EL CASO DE QUE NO AGREGARÁ EL PRODUCTO AL CARRITO
    else:
        # CONSULTA a la base de datos para obtener el producto
        cursor = conexion.connection.cursor()
        cursor.execute("SELECT * FROM productos WHERE id_producto = %s", (producto_id_str,))
        producto = cursor.fetchone()
        cursor.close()
        
        print(f"Producto obtenido de la base de datos: {producto}")  #TEST
        #AGREGA AL CARRITO EL PRODUCTO
        if producto:
            carrito[producto_id_str] = {
                'nombre': producto[2], 
                'precio': float(producto[4]),  # Convertir Decimal a float
                'cantidad': 1
            }
    
    session['carrito'] = carrito
    print(f"Carrito actualizado: {session['carrito']}")  # Verificación del contenido del carrito
    return redirect(url_for('index'))

#ELIMINA LOS PRODUCTOS DEL CARRITO
@app.route('/eliminar_carrito/<string:producto_id>')
def eliminar_carrito(producto_id):
    if 'carrito' in session:
        carrito = session['carrito']
        #SE PASA EN CADENA STRNG
        producto_id_str = producto_id  
        #SI EXISTE EL PRODUCTO ENTRA EN EL IF
        if producto_id_str in carrito:
            #DECREMENTA EL PRODUCTO
            if carrito[producto_id_str]['cantidad'] > 1:
                carrito[producto_id_str]['cantidad'] -= 1
            else:
                del carrito[producto_id_str]
            session['carrito'] = carrito
    return redirect(url_for('ventana_cliente', ir='carrito'))
        
#REALIZA EL PROCESO DE LA COMPRA
@app.route('/realizar_compra')
def realizar_compra():

    aleatorio = stringAleatorio()
    referencia = randint(10000000000000000000, 9999999999999999999999999)
    
    global log
    #VERIFICA SI EL USUARIO ESTÁ LOGEADO
    if log == False:
        flash ('Primero debes de iniciar sesion para comprar nuestros productos','danger')
    
        return redirect(url_for('ventana_cliente', ir = 'carrito'))  # Redirigir si el carrito está vacío """
    else:
        #VERIFICA SI EXISTE ALGO EN EL CARRITO
        if 'carrito' not in session or not session['carrito']:
            flash ('No tienes productos agregados, ¡Conoce más sobre nuestros productos!.', 'warning')
            return redirect(url_for('ventana_cliente', ir = 'carrito'))
        else:
            #POSTERIORMENTE INICIÓ SESION ENTONCES TRAIGO LOS DATOS DEL CLIENTE QUE INICIÓ SESION
            correo = session['correo']
            direccion = session['direccion']
            estado = session['estado']
            pais = session['pais']
            nombre = session['usuario']
            carrito = session['carrito']
            total = sum(item['precio'] * item['cantidad'] for item in carrito.values())
            #ACTUALIZA LA CANTIDAD EXISTENTE DE LO PRODUCTOS A LA HORA DE REALIZAR LA COMPRA
            for producto_id, detalles in carrito.items():
                cursor = conexion.connection.cursor()
                cursor.execute("UPDATE productos SET cant_inventario = cant_inventario - %s WHERE id_producto = %s", (detalles['cantidad'], producto_id))
                conexion.connection.commit()
                cursor.close()

             # INSERTA EN LA TABLA DE PEDIDOS
            cursor = conexion.connection.cursor()
            cursor.execute("INSERT INTO pedidos (id_usuario, fechahora_pedido, estado, total_pedido, direccion_envio) VALUES (%s, %s, %s, %s, %s)", (session['id_usuario'], datetime.now(), 'Pendiente', total, session['pais']+", "+session['estado']+", "+session['direccion']))
            conexion.connection.commit()
            id_pedido = cursor.lastrowid
            cursor.close()

            # INSERTA EN LA TABLA DE DETALLES PEDIDO
            for producto_id, detalles in carrito.items():
                cursor = conexion.connection.cursor()
                cursor.execute("INSERT INTO detallesPedido (id_pedido, id_producto, cantidad, precio_unitario) VALUES (%s, %s, %s, %s)", (id_pedido, producto_id, detalles['cantidad'], detalles['precio']))
                conexion.connection.commit()
                cursor.close()
            
            
            # GENERA EL TICKET EN PDF
            pdf_buffer = BytesIO()
            cabecera_path = os.path.join(os.path.dirname(__file__), 'static', 'img', 'cabecera.png')
            pie_path = os.path.join(os.path.dirname(__file__), 'static', 'img', 'pie.png')
            c = canvas.Canvas(pdf_buffer, pagesize=letter)
            # Dibujar cabecera (ajustada para abarcar todo el ancho)
            c.drawImage(cabecera_path, 0, 750, width=letter[0], height=50)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(100, 730, f"¡Gracias por comprar en Farmacias Amixes, {nombre}!")
            c.setFont("Helvetica", 10)
            c.drawString(100, 715, f"Fecha del pedido: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            c.drawString(100, 700, f"Dirección de envío: {direccion}, {estado}, {pais}")
            c.drawString(100, 685, f"Número de pedido: {aleatorio}")
            c.drawString(100, 670, "Adjuntamos los productos que solicitaste junto con su precio:")

            # Desglose de productos
            y = 650
            for producto_id, detalles in carrito.items():
                c.drawString(100, y, f"{detalles['nombre']} - {detalles['cantidad']} x ${detalles['precio']:.2f}")
                y -= 20

            c.drawString(100, y, f"Total: ${total:.2f}")
            y -= 40
            c.drawString(100, y, f"PAGAR CON ESTE NUMERO DE REFERENCIA: {referencia}")
            # Mensaje de agradecimiento y despedida
            y -= 40
            c.drawString(100, y, "Para seguir el estado de tus productos, visita nuestra página web o contacta a nuestro servicio al cliente.")
            y -= 20
            c.drawString(100, y, "Contactanos por correo: farmaciasamixes@gmail.com.")
            y -= 20
            c.drawString(100, y, "Teléfono: +52 (55) 9945 2451")
            y -= 20
            c.drawString(100, y, "¡Esperamos verte pronto! Gracias por confiar en Farmacias Amixes.")

            # Dibujar pie de página (ajustado para abarcar todo el ancho)
            c.drawImage(pie_path, 0, 0, width=letter[0], height=100)

            c.showPage()
            c.save()
            pdf_buffer.seek(0)

            # Enviar el correo electrónico con el ticket adjunto
            msg = Message("Ticket de Compra", sender="your-email@example.com", recipients=[correo])
            msg.body = "Gracias por tu compra. Adjuntamos tu ticket de compra en formato PDF."
            msg.attach("ticket_compra_FARMACIAS_AMIXES.pdf", "application/pdf", pdf_buffer.getvalue())

            mail.send(msg)

            # Vaciar el carrito después de la compra
            session.pop('carrito', None)
            flash('El ticket de compra fue enviado a tu correo, para mas aclaraciones: <a href="mailto:farmaciasamixes@gmail.com" class="nav-link px-2 ">farmaciasamixes@gmail.com</a>', 'info')

            return redirect(url_for('ventana_cliente',ir = 'carrito'))

#REDIRECCION DE LAS VENTANAS DEL ADMIN
@app.route('/admin')
def ventana_admin():
    ventana = request.args.get('ir')
    categorias_existentes = llenar_categorias()
    mostrar = mostrar_productos()
    
    if ventana == 'inicio':
        return render_template('/admin/inicio.html')
    if ventana == 'productos':
        return render_template('admin/productos.html', mostrar = mostrar)
    if ventana == 'pedidos':

        cursor = conexion.connection.cursor()
        cursor.execute("SELECT p.id_pedido, CONCAT( u.nombre, ' ', u.apellidos ) AS nombre_completo, p.fechahora_pedido, p.total_pedido, p.direccion_envio, p.estado FROM pedidos p JOIN usuarios u ON u.id_usuario = p.id_usuario")
        pedidos = cursor.fetchall()
        cursor.close()
        return render_template('admin/pedidos.html', pedidos = pedidos)
    if ventana == 'clientes':

        clientes = buscar_clientes(1,None)
        return render_template('admin/clientes.html', clientes = clientes)
    if ventana == 'registrar':
        return render_template('admin/registro_cliente.html')
    if ventana == 'actualizarUsuario':
        id = request.args.get('id')

        cursor = conexion.connection.cursor()
        cursor.execute("SELECT * FROM farmacia.usuarios WHERE id_usuario = %s", (id,))
        cliente = cursor.fetchone()
        cursor.close()
        return render_template('admin/editar_cliente.html', clientes = cliente)
    if ventana == 'eliminarUsuario':
        id = request.args.get('id')
        cursor = conexion.connection.cursor()
        sql = "UPDATE usuarios SET estado_usuario = 'deshabilitado' WHERE id_usuario = %s"
        cursor.execute(sql, (id,))
        conexion.connection.commit()
        cursor.close()
        return redirect(url_for('ventana_admin', ir = 'clientes'))
    if ventana == 'agregarProducto':
        return render_template('admin/registro_productos.html', categorias_existentes = categorias_existentes)
    if ventana == 'agregarCategoria':
        return render_template('admin/categorias.html', categorias_existentes = categorias_existentes)

#EL BOTON BUSCAR EN CLIENTES DEL ADMIN, REALIZARÁ LA BUSQUEDA DEACUERDO AL NOMBRE
@app.route('/busqueda_cliente', methods=['POST', 'GET'])
def busqueda_cliente():
    #SI EL METODO ES POST ENTRARÁ
    if request.method == 'POST':
        #OBTENGO EL NOMBRE DEL SEARCH EN EL HTML
        nombre = request.form.get('nombre_cliente')
        try:
            cursor = conexion.connection.cursor()
            print(nombre)
            cursor.execute("SELECT * FROM farmacia.usuarios WHERE nombre = %s", (nombre,))
            datos_usuario = cursor.fetchall()
            cursor.close()
            # Renderiza la plantilla 'clientes.html' y pasa los datos de los usuarios como contexto
            return render_template('admin/clientes.html', clientes = datos_usuario)
            
        except Exception as ex:
            print("Error al buscar usuario:", ex)
            return "Error al recuperar los usuarios"

#FUNCION DE LOS BOTONES DE PRODUCTOS -EDITAR -ELIMINAR
@app.route('/adminProductos' , methods = ['POST', 'GET'])
def botonesProductos(): 
     if request.method == 'POST':
        realizar = request.args.get('tipo')
        id_producto = request.args.get('id')
        data = llenar_categorias()
        if(realizar == 'editar'):
            print("tipo: "+realizar)
            producto = encontrarProducto(id_producto)
            return render_template('admin/editar_productos.html', producto = producto, data = data)
        if(realizar == 'eliminar'):
            eliminar_productos(id_producto)
            return redirect('/admin?ir=productos')
            
#BUSCA LOS CLIENTES A MOSTRAR EN LA VISTA DE LOS CLIENTES DEL ADMIN
def buscar_clientes(des, id_usuario = None):
    if des == 1:
        try:
            cursor = conexion.connection.cursor()
            sql = "SELECT * FROM usuarios WHERE estado_usuario != 'deshabilitado'"
            cursor.execute(sql)
            cat = cursor.fetchall()
            return cat
        except Exception as ex:
            print("Error al obtener los pedidos:", ex)
            return []
    if des == 2:
        try:
            cursor = conexion.connection.cursor()
            sql = "SELECT * FROM usuarios WHERE id_usuario = %s"
            cursor.execute(sql, id_usuario)
            cat = cursor.fetchall()
            return cat
        except Exception as ex:
            print("Error al obtener los pedidos:", ex)
            return []
        
#HACE UNA BUSQUEDA DEL PRODUCTO CUANDO SE EDITA Y DEVUELVE SUS VALORES
def encontrarProducto(id_producto):
    try:
        cursor = conexion.connection.cursor()
        cursor.execute("SELECT * FROM farmacia.productos WHERE id_producto = "+id_producto)
        datos_producto = cursor.fetchall()
        cursor.close()
        return datos_producto
    except Exception as ex:
        print("Error al recuperar productos:", ex)
        return "Error al recuperar el producto"
    
#ELIMINA LOS PRODUCTOS
def eliminar_productos(id_producto):
    try:
        cursor = conexion.connection.cursor()
        
        sql = "DELETE FROM farmacia.productos WHERE id_producto=%s"
        cursor.execute(sql, (id_producto,))
        conexion.connection.commit()
        
        # Cerrar el cursor
        cursor.close()
        return 
    except Exception as ex:
        print("Error al eliminar producto:", ex)
        return str(ex)

#CUENTA EL NUMERO DE LOS PRODUCTOS PARA MOSTRARLO EN UN CIRCULO ARRIBA DE LOS PRODUCTOS
def contar_productos_carrito():
    if 'carrito' in session:
        carrito = session['carrito']
        return sum(item['cantidad'] for item in carrito.values())
    return 0

#REDIRECCION DE LAS VENTANAS DEL CLIENTE
@app.route('/cliente')
def ventana_cliente():
    ventana = request.args.get('ir')
    data = llenar_categorias()
    numero_productos = contar_productos_carrito()
    
    global log
    #ventana pendiente
    if ventana == 'pedidos' and log == True:
        usuario_id = session['id_usuario']
        cursor = conexion.connection.cursor()
        cursor.execute("SELECT * FROM pedidos WHERE id_usuario = %s ORDER BY fechahora_pedido DESC", (usuario_id,))
        pedidos = cursor.fetchall()

        pedidos_con_detalles = []
        for pedido in pedidos:
            cursor.execute("""
                SELECT p.nombre_producto, d.cantidad, d.precio_unitario
                FROM detallesPedido d
                JOIN productos p ON d.id_producto = p.id_producto
                WHERE d.id_pedido = %s
            """, (pedido[0],))
            detalles_pedido = cursor.fetchall()
            pedidos_con_detalles.append((pedido, detalles_pedido))

        cursor.close()
        return render_template('cliente/pedidos.html', data = data, log = log, numero_productos = numero_productos, pedidos = pedidos_con_detalles)
    if ventana == 'nosotros':
        return render_template('cliente/nosotros.html', data = data, log = log, numero_productos = numero_productos)
    if ventana == 'carrito':
        #datos_productos, suma = #busqueda_producto() REGRESA LOS DATOS DE LOS PRODUCTOS Y LA SUMA DE LOS PRODUCTOS
        datos_productos =session.get('carrito', {})
        #suma= 0
        suma = sum(producto['precio'] * producto['cantidad'] for producto in datos_productos.values())
        return render_template('cliente/carrito.html', data = data, datos_productos = datos_productos, numero_productos = numero_productos, suma = suma, log = log)
    if ventana == 'login':
        return render_template('cliente/login.html')
    if ventana == 'registro':
        return render_template('cliente/registro.html')
    if ventana == 'cerrarlogin':
        log = False
        return render_template('cliente/login.html')
    

#REALIZA TODA LA SUMA DE LOS PRODUCTOS PARA MOSTRARLO EN PEDIDOS
def suma_precios(datos_productos):
    suma = 0
    for producto in datos_productos:
        suma += producto[4]  # Asumiendo que el precio está en la posición 4
    return suma

#REGISTRAR PRODUCTOS, AQUI VIENE OTRA FUNCION PARA AGREGAR LAS IMAGENES Y CAMBIA EL NOMBRE DE LA IMAGEN
@app.route('/registrarp', methods = ['POST', 'GET'])
def registrarp():
    if request.method == 'POST':
        categoria_producto = request.form['categoriap']
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        cantidad = request.form['cantidad']
        
        img = request.files['imagen']
        basepath = os.path.dirname(__file__)#DIR DE LA APLICACION
        filename = secure_filename(img.filename)#NOMBRE DE LA IMG

        #SOBRE ESCRIBIENDO NAME
        extensionImg = os.path.splitext(filename)[1]
        nuevoNameImg = stringAleatorio()+extensionImg
        
        guardarImg = os.path.join(basepath, 'static\\productosIMG', nuevoNameImg)
        img.save(guardarImg)
        """ upload_path = os.path.join(basepath, 'static\\productosIMG', nuevoNameImg)
        img.save(upload_path) """
        
        print(nuevoNameImg)
        msj = insert_productos(categoria_producto, nombre,descripcion, precio, cantidad, nuevoNameImg)
        print(msj)
        return redirect('/admin?ir=agregarProducto')
    
#ENTRA CON EL BOTON BUSCAR Y MOSTRARÁ EL PRODUCTO QUE BUSCÓ    
@app.route('/detalles_producto/<string:id_producto>')
def detalles_producto(id_producto):

    numero_productos = contar_productos_carrito()
    producto_id_str = str(id_producto)
    cursor = conexion.connection.cursor()
    cursor.execute("SELECT * FROM productos WHERE id_producto = %s", (producto_id_str,))
    producto = cursor.fetchone()
    cursor.close()
    #ESTA DECISION AVISA SI EL PRODUCTO ESTÁ EN EXISTENCIA, EN EL CASO DE QUE NO ESTARÁ EN TRUE Y MOSTRARÁ DE QUE EL PRODUCO NO LO TENEMOS
    if producto:
        existenciaBD = True
    data = llenar_categorias()
    global log
    return render_template('cliente/detalles.html', log = log, data = data, producto = producto, numero_productos = numero_productos, existenciaBD = existenciaBD)

#BUSCA LOS DETALLES DE LOS PRODUCTOS Y LOS MOSTRARÁ EN SU RESPECTIVO HTML
@app.route('/buscar_producto', methods = ['POST','GET'])    
def buscar_producto():
    
    if request.method == 'POST':
        producto = None
        
        nombreProducto = request.form['buscarProducto']
        cursor = conexion.connection.cursor()
        cursor.execute("SELECT * FROM productos WHERE nombre_producto = %s", (nombreProducto,))
        producto = cursor.fetchone()
        cursor.close()
        if producto is None:
            existenciaBD = False

            producto = {
                'id_producto': 0,
                'id_categoria': '',
                'nombre_producto': '',
                'descripcion': '',
                'precio': 0,
                'cantidad': 0,
                'imagen': ''}
        else:
            existenciaBD = True
        data = llenar_categorias()
        numero_productos = contar_productos_carrito()
    global log
    return render_template('cliente/detalles.html', log = log, data = data, producto = producto, numero_productos = numero_productos, existenciaBD = existenciaBD)

#CAMBIA EL ESTADO DEL PEDIDO -ENTREGADO -CANCELAR
@app.route('/pedido')
def pedido():
    des = request.args.get('des')
    id = request.args.get('id')
    print(des,id)
    if des == 'entregado':
        try:
            cursor = conexion.connection.cursor()
            
            sql = """UPDATE farmacia.pedidos SET estado = 'entregado'
                    WHERE id_pedido=%s"""
            cursor.execute(sql,(id,))
            conexion.connection.commit()
            cursor.close()
            return redirect(url_for('ventana_admin', ir = 'pedidos'))
        except Exception as ex:
            print("Error al cambiar pedido:", ex)
        return
    if des == 'cancelar':
        try:
            cursor = conexion.connection.cursor()
            
            sql = """UPDATE farmacia.pedidos SET estado = 'cancelado'
                    WHERE id_pedido=%s"""
            cursor.execute(sql,(id,))
            conexion.connection.commit()
            cursor.close()
            return redirect(url_for('ventana_admin', ir = 'pedidos'))
        except Exception as ex:
            print("Error al cambiar pedido:", ex)
        return

#BUSCA LOS PRODUCTOS DEACUERDO A LA CATEGORIA
@app.route('/buscar_por_categoria')
def buscar_por_categoria():
    cat = request.args.get('cat')
    cursor = conexion.connection.cursor()
    print(cat)
    #cursor.execute("SELECT * FROM productos WHERE nombre_producto = %s", (cat,))
    cursor.execute("SELECT id_producto, id_categoria, nombre_producto, descripcion, precio, cant_inventario, imagen_url  FROM productos NATURAL JOIN categorias WHERE categoria = %s", (cat,))
    producto = cursor.fetchall()
    cursor.close()
    data = llenar_categorias()
    numero_productos = contar_productos_carrito()
    global log
    return render_template('cliente/categorias.html', log = log, data = data, numero_productos = numero_productos, mostrarP = producto, nombreCategoria = cat)

#CATEGORIAS TOMA LA DECISION A REALIZAR Y REDIRECCIONA A MODULOS CATEGORIA
@app.route('/agregarCategoria', methods = ['POST', 'GET'])
def agregarCategoria():
    
    accion = request.args.get('accion')
    print(accion)
    #DEPENDIENDO LO QUE REALIZARÁ ES LO QUE PEDIRA DE LAS ETOQUETAS
    if(accion == "agregar" and request.method == 'POST'):
        nombre = request.form.get('categoria')
        print(nombre)
        msj  = moduloCategoria(accion, None, nombre)
        return msj
    if(accion == "editar"):
        id = request.form.get('id_categoria')
        nombre = request.form.get('nuevo_nombre')
        msj = moduloCategoria(accion, id, nombre)
        return msj
        
    return "buena"

#MODULO CATEGORIAS -AGREGA -EDITA
def moduloCategoria(accionSQL , id , nombre):
    cursor = conexion.connection.cursor()
    print("MODULOS"+accionSQL)
    #SI MI VARIABLE CONTIENE AGREGAR ENTRARÁ
    if(accionSQL == 'agregar'):
        try:
            sql = """INSERT INTO farmacia.categorias(categoria) 
         VALUES (%s)"""
            cursor.execute(sql,(nombre,))
            conexion.connection.commit()
            # Cerrar el cursor
            cursor.close()
            return redirect("/admin?ir=agregarCategoria")
        except Exception as ex:
            print("Error al agregar categoria:", ex)
        
    #SI MI VARIABLE CONTIENE EDITAR ENTRARÁ
    if(accionSQL == 'editar'):
        try:
            sql = """UPDATE farmacia.categorias SET categoria=%s 
                 WHERE id_categoria=%s"""
            cursor.execute(sql,(nombre, id))
            conexion.connection.commit()
            # Cerrar el cursor
            cursor.close()
            return redirect("/admin?ir=agregarCategoria")
        except Exception as ex:
            print("Error al crear usuario:", ex)
    
    return

#ACTUALIZAR PRODUCTOS
@app.route('/actualizarp', methods = ['POST', 'GET'])
def actualizarp():
    if request.method == 'POST':
        id_producto = request.args.get('id')
        categoria_producto = request.form['categoriap']
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        cantidad = request.form['cantidad']
        
        img = request.files['imagen']
        basepath = os.path.dirname(__file__)#DIR DE LA APLICACION
        filename = secure_filename(img.filename)#NOMBRE DE LA IMG

        #SOBRE ESCRIBIENDO NAME
        extensionImg = os.path.splitext(filename)[1]
        nuevoNameImg = stringAleatorio()+extensionImg
        
        guardarImg = os.path.join(basepath, 'static\\productosIMG', nuevoNameImg)
        img.save(guardarImg)
        """ upload_path = os.path.join(basepath, 'static\\productosIMG', nuevoNameImg)
        img.save(upload_path) """

        print(nuevoNameImg)
        msj = actualizar_productos(categoria_producto, nombre,descripcion, precio, cantidad, nuevoNameImg, id_producto)
        print(msj)
        return "buena bro"

#ACTUALIZAR PRODUCTOS
def actualizar_productos(categoria_producto, nombre,descripcion, precio, cantidad, url, id_producto):
    try:
        cursor = conexion.connection.cursor()
        
        sql = """UPDATE farmacia.productos SET id_categoria=%s, nombre_producto=%s, descripcion=%s, precio=%s, cant_inventario=%s, imagen_url=%s 
                 WHERE id_producto=%s"""
        cursor.execute(sql,(categoria_producto, nombre, descripcion, precio, cantidad, url, id_producto))
        conexion.connection.commit()
        # Cerrar el cursor
        cursor.close()
        return "buena"
    except Exception as ex:
        print("Error al crear usuario:", ex)
    return

#CONSULTAR PRODUCTOS EN INICIO CLIENTES
def mostrar_productos():
    try:
        cursor = conexion.connection.cursor()
        cursor.execute("SELECT * FROM farmacia.productos")
        productos = cursor.fetchall()
        cursor.close()
        return productos
    except Exception as ex:
        print("Error al recuperar productos:", ex)
        return "Error al recuperar productos"

#GENERAR UN STRING ALEATORIO PARA LAS IMAGENES
def stringAleatorio():
    string_Aleatorio = "0123456789abcdefghijklmnopqrstuvwxyz_"
    longitud = 20
    secuencia = string_Aleatorio.upper()
    result = sample(secuencia, longitud)
    string_Aleatorio = "".join(result)
    return string_Aleatorio

#INSERTAR PRODUCTOS
def insert_productos(categoria_producto, nombre,descripcion, precio, cantidad, url):
    try:
        cursor = conexion.connection.cursor()
        
        sql = """INSERT INTO farmacia.productos(id_categoria, nombre_producto, descripcion, precio, cant_inventario, imagen_url) 
         VALUES (%s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql,(categoria_producto, nombre, descripcion, precio, cantidad, url))
        conexion.connection.commit()
        # Cerrar el cursor
        cursor.close()
        return "buena"
    except Exception as ex:
        print("Error al crear usuario:", ex)
    return
    
#REGISTRA SU USUARIO EL MISMO USUARIO
@app.route('/registrar', methods = ['POST','GET'])    
def registrar():
    param = request.args.get('param')
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellidos = request.form['apellidos']
        
        pais = request.form['pais']
        estado = request.form['estado']
        direccion = request.form['direccion']
        correo = request.form['correo']
        contraseña = request.form['contraseña']        
        tipo = "cliente"
        insert_usuarios(nombre,apellidos,correo,contraseña,direccion,estado,pais, tipo, param)
        flash('¡Inicia sesion con tu cuenta creada!', 'primary')
        return render_template('cliente/login.html')
        


    else:
        return "Usuario no registrado"


#VALIDAR ACCESOS
@app.route('/validar', methods = ['POST','GET'])    
def autentificacion():
    
    if request.method == 'POST':
        correo = request.form['correo']
        pwd = request.form['contraseña']

        
        #user = Users(0,None,None, correo, pwd, None, None, None, None, None)
        #sesion, tipo_sesion = ModelsUsers.login(0,conexion, user)
        cursor = conexion.connection.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE correo=%s AND contraseña=%s", (correo, pwd))
        user = cursor.fetchone()
        if user:
            session['id_usuario'] = user [0]
            session['usuario'] = user[1]
            session['direccion'] = user[6]
            session['pais'] = user[9]
            session['estado'] = user[8]
            session['correo'] = user[3]
            #OBTENIENDO EL TIPO DE USUARIO
            session['tipo_usuario'] = user[5]
            global log
            
            print("BIENVENIDO")
            if session['tipo_usuario'] == "cliente":
                #print(tipo_sesion)
                log = True
                return redirect(url_for('index'))
            if session['tipo_usuario'] == "administrador":
                #print(tipo_sesion)
                
                return render_template('admin/inicio.html')
        else:
            flash("Usuario no encontrado", "danger")
            #return render_template('cliente/login.html')
            return redirect(url_for('ventana_cliente', ir='login'))


    else:
        print("Error de autentificación")
        return render_template('cliente/login.html')

def query_string():
    return "Ok"

#LLENAR CATEGORIAS
def llenar_categorias():
    
    try:
        cursor = conexion.connection.cursor()
        sql = "SELECT * FROM categorias"
        cursor.execute(sql)
        cat = cursor.fetchall()
        return cat
    except Exception as ex:
        print("Error al obtener las categorías:", ex)
        return []

#INSERTAR USUAROS
def insert_usuarios(nombre,apellidos,correo,contraseña,direccion,estado,pais, tipo, param):
    if param == True:
        tipo = "Administrador"

    try:
        cursor = conexion.connection.cursor()
        
        sql = """INSERT INTO farmacia.usuarios(nombre, apellidos, correo, contraseña, tipo_usuario, direccion, estado, pais) 
         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql,(nombre,apellidos,correo,contraseña,tipo,direccion,estado,pais))
        conexion.connection.commit()
        # Cerrar el cursor
        cursor.close()
    except Exception as ex:
        print("Error al crear usuario:", ex)
    return

#CIERRA LA SESISON
@app.route('/logout')
def logout():
    #CIERRO LA SESION HACIENDO USO DE SESSION
    session.pop('usuario', None)
    flash('Sesión cerrada', 'info')
    #MI VARIABLE GLOBAL CAMBIA A FALSE
    global log
    log = False

    return redirect(url_for('ventana_cliente',ir = "login"))

#CANCELAR EL PEDIDO
@app.route('/cancelar_pedido/<int:pedido_id>')
def cancelar_pedido(pedido_id):
    cursor = conexion.connection.cursor()
    cursor.execute("UPDATE pedidos SET estado = 'proceso de cancelación' WHERE id_pedido = %s", (pedido_id,))
    conexion.connection.commit()
    cursor.close()
    #LOS MENSAJES FLASH SON MENSAJES QUE ME PERMITE MANDAR A MIS HTML PARA IMPRIMER MENSAJES
    flash('El pedido ha sido cancelado exitosamente.', 'info')
    return redirect(url_for('ventana_cliente', ir = 'pedidos'))

#ACTUALIZARÁ EL CLIENTE 
@app.route('/actualizar_cliente', methods=['POST'])
def actualizar_cliente():
    if request.method == 'POST':
        #OBTENGO LOS DATOS A ACTUALIZAR DEL CLIENTE
        id_usuario = request.form.get('id_usuario')
        nombre = request.form.get('nombre')
        apellidos = request.form.get('apellidos')
        tipo_usuario = request.form.get('tipoUsuario')
        pais = request.form.get('pais')
        estado = request.form.get('estado')
        direccion = request.form.get('direccion')
        correo = request.form.get('correo')
        contraseña = request.form.get('contraseña')
        #REALIZAR LA ACTUALIZACION CON EL USO DE MIS VARIABLES
        try:
            cursor = conexion.connection.cursor()
            sql = """UPDATE farmacia.usuarios 
                     SET nombre=%s, apellidos=%s, tipo_usuario=%s, pais=%s, estado=%s, direccion=%s, correo=%s, contraseña=%s 
                     WHERE id_usuario=%s"""
            cursor.execute(sql, (nombre, apellidos, tipo_usuario, pais, estado, direccion, correo, contraseña, id_usuario))
            conexion.connection.commit()
            cursor.close()
            return redirect(url_for('ventana_admin', ir = 'clientes' ))  # Redirige a la vista de usuarios después de la actualización
        except Exception as ex:
            print("Error al actualizar usuario:", ex)
            return "Error al actualizar el usuario"

#REDIRIGIR A LA PAGINA PRINCIPAL EN CASO DE QUE CAMBIEN LA URL
def pagina_no_encontrada(error):
    return redirect(url_for('index'))



#EJECUCION DE LA PAGINA    
if __name__ ==  '__main__':
    app.config.from_object(config['credencialesDB'])
    app.add_url_rule('/query_string', view_func=query_string)
    app.register_error_handler(404, pagina_no_encontrada)
    app.run(debug=True, port=5000)

