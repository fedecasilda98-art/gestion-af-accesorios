import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# --- DIRECTORIOS Y ARCHIVOS ---
if not os.path.exists("data"):
    os.makedirs("data")

ARCHIVO_ARTICULOS = "data/lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "data/clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "data/movimientos_clientes.csv"
CARPETA_FOTOS = "data/fotos_productos"
WHATSAPP_NUM = "5493413512049"

if not os.path.exists(CARPETA_FOTOS): 
    os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columns):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            for col in columns:
                if col not in df.columns: 
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo"]) else ""
            for col in df.columns:
                if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock"]):
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
            return df[columns]
        except: 
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)

# --- ESTADOS DE SESIÓN ---
if "carrito" not in st.session_state: st.session_state.carrito = []
if "remito_items" not in st.session_state: st.session_state.remito_items = []
if "confirmar_orden" not in st.session_state: st.session_state.confirmar_orden = False
if "confirmar_nc" not in st.session_state: st.session_state.confirmar_nc = False

# --- UTILIDADES ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True, align="C")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True, align="C")
        self.ln(10)

def generar_pdf_binario(cliente_nombre, carrito, total, df_clientes, titulo="PRESUPUESTO", fecha_fija=None):
    try:
        datos_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(datos_cli["Tel"].values[0]) if not datos_cli.empty else "-"
        loc = str(datos_cli["Localidad"].values[0]) if not datos_cli.empty else "-"
        dir = str(datos_cli["Direccion"].values[0]) if not datos_cli.empty else "-"
        fecha = fecha_fija if fecha_fija else datetime.now().strftime("%d/%m/%Y %H:%M")

        pdf = FPDF()
        pdf.add_page()
        
        # --- ENCABEZADO ---
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True)
        pdf.ln(5)

        # --- RECUADRO GRIS TIPO DOC ---
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {titulo}", border=1, ln=True, fill=True)

        # --- GRILLA CLIENTE ---
        pdf.set_font("Arial", "B", 10)
        pdf.cell(95, 8, f" CLIENTE: {cliente_nombre}", border="LR")
        pdf.cell(0, 8, f" FECHA: {fecha}", border="R", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(95, 8, f" TEL: {tel}", border="LR")
        pdf.cell(0, 8, f" LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(0, 8, f" DIRECCIÓN: {dir}", border="LRB", ln=True)
        pdf.ln(5)

        # --- CONTENIDO SEGÚN EL TIPO DE DOCUMENTO ---
        if titulo == "RECIBO DE PAGO":
            # Estructura limpia para Recibos de Entrega de Dinero
            pdf.set_fill_color(200, 200, 200)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(140, 8, " Concepto / Detalle de Entrega", 1, 0, "L", fill=True)
            pdf.cell(50, 8, "Total Abonado", 1, 1, "C", fill=True)

            pdf.set_font("Arial", "", 10)
            for item in carrito:
                pdf.cell(140, 8, f" {item['Producto']}", 1)
                pdf.cell(50, 8, formatear_moneda(item['Subtotal']), 1, 1, "R")
        else:
            # Estructura tradicional para Presupuestos, Ventas, Remitos y Notas de Crédito
            pdf.set_fill_color(200, 200, 200)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(110, 8, " Articulo / Accesorio", 1, 0, "L", fill=True)
            pdf.cell(15, 8, "Cant.", 1, 0, "C", fill=True)
            pdf.cell(30, 8, "P. Unit", 1, 0, "C", fill=True)
            pdf.cell(35, 8, "Subtotal", 1, 1, "C", fill=True)

            pdf.set_font("Arial", "", 10)
            for item in carrito:
                p_u = item['Subtotal'] / item['Cant'] if item['Cant'] > 0 else 0
                pdf.cell(110, 8, f" {item['Producto']}", 1)
                pdf.cell(15, 8, str(item['Cant']), 1, 0, "C")
                pdf.cell(30, 8, formatear_moneda(p_u), 1, 0, "R")
                pdf.cell(35, 8, formatear_moneda(item['Subtotal']), 1, 1, "R")

        # --- TOTAL EN EL PIE ---
        pdf.set_font("Arial", "B", 12)
        if titulo == "RECIBO DE PAGO":
            pdf.cell(140, 10, "MONTO TOTAL RECIBIDO: ", 0, 0, "R")
            pdf.cell(50, 10, f" {formatear_moneda(total)}", 1, 1, "R")
        else:
            pdf.cell(125, 10, "TOTAL: ", 0, 0, "R")
            pdf.cell(35, 10, f" {formatear_moneda(total)}", 1, 1, "R")

        res = pdf.output(dest='S')
        return bytes(res) if not isinstance(res, str) else res.encode('latin-1', 'replace')
    except Exception as e:
        return b""

# --- INTERFAZ PRINCIPAL ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre", "📦 Remitos"])

with tabs[0]: # STOCK
    st.header("Inventario Actual")
    if not df_stock.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Costo Stock", formatear_moneda((df_stock['Costo Base'] * df_stock['Stock']).sum()))
        c2.metric("Total Lista 1", formatear_moneda((df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()))
        c3.metric("Total Lista 2", formatear_moneda((df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()))
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # 🚚 LOTE
    st.header("🚚 Gestión de Inventario (Lote)")
    
    sub_tab_existente, sub_tab_nuevo = st.tabs(["🔄 Reponer Existente", "🆕 Cargar Producto Nuevo"])
    
    with sub_tab_existente:
        st.subheader("Reposición de Stock")
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                prod_repo = st.selectbox("Seleccionar Producto para reponer:", 
                                       df_stock["Accesorio"].tolist(), 
                                       key="repo_prod_select")
            with col2:
                cant_repo = st.number_input("Cantidad que ingresa:", min_value=1, value=1, key="repo_cant")
            with col3:
                nuevo_costo = st.number_input("Nuevo Costo Base (opcional):", min_value=0.0, value=0.0, key="repo_costo")
        
        if st.button("➕ Confirmar Ingreso de Stock", use_container_width=True):
            idx = df_stock[df_stock["Accesorio"] == prod_repo].index[0]
            df_stock.at[idx, "Stock"] += cant_repo
            
            # Guardamos el costo para registrar en el historial (el nuevo o el que ya tenía)
            costo_registro = nuevo_costo if nuevo_costo > 0 else float(df_stock.at[idx, "Costo Base"])
            
            if nuevo_costo > 0:
                df_stock.at[idx, "Costo Base"] = nuevo_costo
                flete = df_stock.at[idx, "Flete"]
                ganancia = df_stock.at[idx, "% Ganancia"]
                l1 = (nuevo_costo + flete) * (1 + ganancia / 100)
                df_stock.at[idx, "Lista 1 (Cheques)"] = round(l1, 2)
                df_stock.at[idx, "Lista 2 (Efectivo)"] = round(l1 * 0.90, 2)
            
            df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
            
            # --- REGISTRO EN HISTORIAL DE CARGAS (UNIFICADO) ---
            n_carga = pd.DataFrame([{
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Cliente": "INTERNO (LOGÍSTICA)",
                "Tipo": "INGRESO STOCK",
                "Monto": costo_registro,
                "Metodo": f"Cant: {cant_repo}",
                "Detalle": f"Reposición: {prod_repo}"
            }])
            pd.concat([df_movs, n_carga]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
            
            st.success(f"Stock actualizado: {prod_repo}")
            st.rerun()

    with sub_tab_nuevo:
        st.subheader("Alta de Nuevo Producto")
        with st.form("form_nuevo_producto", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                n_rubro = st.text_input("Rubro")
                n_prov = st.text_input("Proveedor")
                n_acc = st.text_input("Nombre del Accesorio")
            with c2:
                n_stock = st.number_input("Stock Inicial", min_value=0, value=0)
                n_costo = st.number_input("Costo Base $", min_value=0.0, format="%.2f")
                n_flete = st.number_input("Flete $", min_value=0.0, format="%.2f")
            with c3:
                n_gan = st.number_input("% Ganancia", min_value=0.0, value=40.0)
                n_desc = st.text_area("Descripción")
            
            # Botón de envío (Corregido sin el atributo que fallaba)
            submit_nuevo = st.form_submit_button("🚀 Dar de Alta Producto")
            
            if submit_nuevo:
                if n_acc == "":
                    st.error("El nombre del accesorio es obligatorio.")
                else:
                    l1_new = (n_costo + n_flete) * (1 + n_gan / 100)
                    nuevo_item = {
                        "Rubro": n_rubro,
                        "Proveedor": n_prov,
                        "Accesorio": n_acc,
                        "Stock": n_stock,
                        "Costo Base": n_costo,
                        "Flete": n_flete,
                        "% Ganancia": n_gan,
                        "Lista 1 (Cheques)": round(l1_new, 2),
                        "Lista 2 (Efectivo)": round(l1_new * 0.90, 2),
                        "Descripcion": n_desc
                    }
                    df_stock = pd.concat([df_stock, pd.DataFrame([nuevo_item])], ignore_index=True)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    
                    # --- REGISTRO EN HISTORIAL DE CARGAS (UNIFICADO) ---
                    n_alta = pd.DataFrame([{
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Cliente": "INTERNO (LOGÍSTICA)",
                        "Tipo": "ALTA PROD",
                        "Monto": n_costo,
                        "Metodo": f"Cant Inicial: {n_stock}",
                        "Detalle": f"Producto Nuevo: {n_acc}"
                    }])
                    pd.concat([df_movs, n_alta]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    
                    st.success(f"Producto {n_acc} creado.")
                    st.rerun()

    # --- NUEVA SECCIÓN: GRILLA DE HISTORIAL EN LOTE ---
    st.markdown("---")
    st.subheader("📋 Historial de Cargas Realizadas")
    
    # Filtramos para que en esta pestaña solo se listen las acciones logísticas
    historial_cargas = df_movs[df_movs["Tipo"].isin(["INGRESO STOCK", "ALTA PROD"])].copy()
    
    if not historial_cargas.empty:
        # Mostramos los ingresos más recientes arriba de todo
        historial_cargas = historial_cargas.sort_index(ascending=False)
        
        # Armamos un formato limpio para leer rápido en pantalla
        vista_cargas = pd.DataFrame({
            "Fecha y Hora": historial_cargas["Fecha"],
            "Tipo Movimiento": historial_cargas["Tipo"],
            "Artículo / Accesorio": historial_cargas["Detalle"],
            "Cantidad Registrada": historial_cargas["Metodo"],
            "Costo Base ($)": historial_cargas["Monto"].apply(formatear_moneda)
        })
        
        st.dataframe(vista_cargas, use_container_width=True, hide_index=True)
    else:
        st.info("No se registran movimientos de carga o reabastecimiento en este período.")

with tabs[2]: # ⚙️ MAESTRO
    st.header("⚙️ Maestro de Artículos")
    
    # Sección de Edición Rápida
    st.subheader("Edición General de Precios y Datos")
    df_ed = st.data_editor(
        df_stock, 
        use_container_width=True, 
        hide_index=True, 
        key="ed_maestro_definitivo"
    )
    
    if st.button("💾 Guardar Cambios en la Tabla", use_container_width=True):
        # Recalcular precios por si se tocó Costo, Flete o Ganancia en la tabla
        df_ed["Lista 1 (Cheques)"] = ((df_ed["Costo Base"] + df_ed["Flete"]) * (1 + df_ed["% Ganancia"] / 100)).round(2)
        df_ed["Lista 2 (Efectivo)"] = (df_ed["Lista 1 (Cheques)"] * 0.90).round(2)
        
        df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
        st.success("✅ Base de datos actualizada correctamente.")
        st.rerun()

    st.markdown("---")
    
    # Sección de Eliminación
    st.subheader("🗑️ Eliminar Artículos")
    with st.expander("Abrir panel de eliminación"):
        st.warning("Cuidado: Eliminar un artículo es una acción permanente.")
        col_del1, col_del2 = st.columns([3, 1])
        
        with col_del1:
            art_a_eliminar = st.selectbox(
                "Seleccionar artículo para borrar:", 
                ["Seleccione uno..."] + df_stock["Accesorio"].tolist(),
                key="delete_art_select"
            )
        
        with col_del2:
            st.write(" ") # Espaciador
            btn_eliminar = st.button("❌ ELIMINAR", use_container_width=True)

        if btn_eliminar:
            if art_a_eliminar != "Seleccione uno...":
                # Filtrar el DataFrame para quitar el artículo
                df_stock = df_stock[df_stock["Accesorio"] != art_a_eliminar]
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                st.error(f"Se ha eliminado: {art_a_eliminar}")
                st.rerun()
            else:
                st.info("Por favor, selecciona un artículo válido.")

with tabs[3]: # 👥 CTA CTE (REDISEÑADO)
    st.header("👥 Gestión de Clientes y Cuentas Corrientes")
    
    sub_ctacte, sub_gestion_clientes = st.tabs(["💰 Estado de Cuenta", "📝 Administrar Clientes"])
    
    with sub_ctacte:
        if not df_clientes.empty:
            c1, c2 = st.columns([2, 1])
            with c1:
                cli_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="ctacte_cli_sel")
            
            idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
            saldo_actual = df_clientes.at[idx_c, "Saldo"]
            
            with c2:
                st.metric("Saldo Pendiente", formatear_moneda(saldo_actual))

            # Inicializamos el carrito temporal de pagos en el session_state si no existe
            if "carrito_pagos" not in st.session_state:
                st.session_state.carrito_pagos = []

            # --- SECCIÓN DE PAGOS (MULTIMÉTODO TIPO CARRITO) ---
                st.subheader("Registrar Pago / Entrega Múltiple")
            
            with st.container(border=True):
                st.markdown("##### ➕ Añadir Línea de Cobro")
                f1, f2, f3 = st.columns([1.5, 1.5, 1])
                with f1:
                    forma_p = st.selectbox("Forma de Pago:", ["Efectivo", "Transferencia", "Cheque", "Echeq"], key="multi_forma_p")
                with f2:
                    monto_p = st.number_input("Monto $:", min_value=0.0, format="%.2f", key="multi_monto_p")
                with f3:
                    fecha_p = st.date_input("Fecha de cobro:", datetime.now(), key="multi_fecha_p")
                
                # Despliegue dinámico de campos si el método requiere tracking de valores (cheques)
                detalles_item = ""
                if forma_p in ["Cheque", "Echeq"]:
                    st.markdown("**📝 Detalles del Título:**")
                    d1, d2, d3 = st.columns(3)
                    n_cheque = d1.text_input("Número de Cheque / Echeq", key="multi_n_cheque")
                    b_cheque = d2.text_input("Banco", key="multi_b_cheque")
                    v_cheque = d3.date_input("Vencimiento", key="multi_v_cheque")
                    detalles_item = f"{forma_p} N°{n_cheque} - {b_cheque} (Vto: {v_cheque.strftime('%d/%m/%Y')})"
                else:
                    detalles_item = st.text_input("Nota adicional (opcional):", key="multi_nota")
                    if not detalles_item:
                        detalles_item = f"Entrega en {forma_p}"

                # Botón intermedio para meter la línea al desglose temporal
                if st.button("➕ AGREGAR FORMA DE PAGO", use_container_width=True):
                    if monto_p <= 0:
                        st.error("El monto debe ser mayor a 0.")
                    elif forma_p in ["Cheque", "Echeq"] and (not n_cheque or not b_cheque):
                        st.error("Por favor, completá el número y el banco del cheque.")
                    else:
                        st.session_state.carrito_pagos.append({
                            "Forma": forma_p,
                            "Monto": monto_p,
                            "Fecha": fecha_p.strftime("%d/%m/%Y"),
                            "Detalle": detalles_item
                        })
                        st.rerun()

            # --- GRILLA VISUAL DEL DETALLE CARGADO ---
            if st.session_state.carrito_pagos:
                st.markdown("##### 📝 Desglose del Recibo Actual")
                
                # Encabezados de tabla simples
                th1, th2, th3, th4 = st.columns([1.5, 3.5, 1.5, 0.5])
                th1.markdown("**Forma**")
                th2.markdown("**Detalle / Título**")
                th3.markdown("**Monto**")
                th4.markdown("")
                
                for idx, p_item in enumerate(st.session_state.carrito_pagos):
                    with st.container(border=True):
                        col_f, col_d, col_m, col_x = st.columns([1.5, 3.5, 1.5, 0.5])
                        col_f.write(p_item["Forma"])
                        col_d.write(p_item["Detalle"])
                        col_m.write(formatear_moneda(p_item["Monto"]))
                        
                        # Cruz rápida para remover renglones mal cargados
                        if col_x.button("❌", key=f"del_pago_item_{idx}", help="Eliminar línea"):
                            st.session_state.carrito_pagos.pop(idx)
                            st.rerun()
                
                total_cobrado = sum(item["Monto"] for item in st.session_state.carrito_pagos)
                st.write(f"### TOTAL RECIBIDO: {formatear_moneda(total_cobrado)}")
                
                # Confirmación final y escritura en bases de datos
                if st.button("📥 CONFIRMAR COBRO TOTAL E IMPACTAR SALDO", use_container_width=True, type="primary"):
                    # 1. Descontar el total acumulado del saldo del cliente
                    df_clientes.at[idx_c, "Saldo"] -= float(total_cobrado)
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    
                    # 2. Compilar strings limpios para guardar un renglón resumen en el historial general
                    resumen_metodos = ", ".join([f"{item['Forma']}: {formatear_moneda(item['Monto'])}" for item in st.session_state.carrito_pagos])
                    detalles_completos = " // ".join([item["Detalle"] for item in st.session_state.carrito_pagos])
                    
                    n_mov = pd.DataFrame([{
                        "Fecha": datetime.now().strftime("%d/%m/%Y"),
                        "Cliente": cli_sel,
                        "Tipo": "PAGO",
                        "Monto": total_cobrado,
                        "Metodo": resumen_metodos[:50],  # Recorte seguro para visualización de tabla
                        "Detalle": detalles_completos[:150]
                    }])
                    df_movs = pd.concat([df_movs, n_mov], ignore_index=True)
                    df_movs.to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    
                    # 3. Almacenar copias profundas en session_state para la descarga externa del PDF
                    st.session_state.pago_procesado_ctacte = True
                    st.session_state.monto_p_ultimo = total_cobrado
                    st.session_state.carrito_p_ultimo = list(st.session_state.carrito_pagos)
                    st.session_state.fecha_p_ultimo = datetime.now().strftime("%d/%m/%Y %H:%M")
                    
                    # Vaciamos la mesa de trabajo del carrito de pagos
                    st.session_state.carrito_pagos = []
                    st.rerun()

            # --- CASILLERO DE DESCARGA DE RECIBO (AFUERA DE LOS CONTENEDORES DE CARGA) ---
            if st.session_state.get("pago_procesado_ctacte", False):
                with st.container(border=True):
                    st.success(f"¡Cobro combinado de {formatear_moneda(st.session_state.monto_p_ultimo)} asentado con éxito!")
                    
                    # Transformamos el desglose guardado al formato que espera tu función maestra
                    items_recibo = []
                    for item in st.session_state.carrito_p_ultimo:
                        items_recibo.append({
                            "Producto": item["Detalle"],
                            "Cant": 1,
                            "Subtotal": item["Monto"]
                        })
                    
                    pdf_recibo = generar_pdf_binario(
                        cli_sel, 
                        items_recibo, 
                        st.session_state.monto_p_ultimo, 
                        df_clientes, 
                        "RECIBO DE PAGO", 
                        st.session_state.fecha_p_ultimo
                    )
                    
                    st.download_button(
                        label="🖨️ DESCARGAR RECIBO DE COBRO COMPUESTO (PDF)",
                        data=pdf_recibo,
                        file_name=f"Recibo_Cobro_{cli_sel.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="btn_download_recibo_instantaneo"
                    )
                    
                    if st.button("🔄 Finalizar y Limpiar Operación", use_container_width=True):
                        st.session_state.pago_procesado_ctacte = False
                        if "carrito_p_ultimo" in st.session_state: 
                            del st.session_state.carrito_p_ultimo
                        st.rerun()

            # --- HISTORIAL ESPECÍFICO Y RE-DESCARGA (CON ELIMINACIÓN SEGURA) ---
            st.subheader(f"Movimientos de {cli_sel}")
            historial_cli = df_movs[df_movs["Cliente"] == cli_sel].sort_index(ascending=False)
            
            if not historial_cli.empty:
                for i, row in historial_cli.iterrows():
                    with st.container(border=True):
                        col_info, col_btn, col_del = st.columns([3, 1, 1])
                        
                        with col_info:
                            st.write(f"**{row['Fecha']}** | {row['Tipo']} | **{formatear_moneda(row['Monto'])}**")
                            st.caption(f"Método: {row['Metodo']} | Detalle: {row['Detalle']}")
                        
                        with col_btn:
                            if row['Tipo'] in ["VENTA", "N. CRÉDITO"]:
                                items_fake = [{"Producto": row['Detalle'], "Cant": 1, "Precio U.": row['Monto'], "Subtotal": row['Monto']}]
                                pdf_data = generar_pdf_binario(cli_sel, items_fake, row['Monto'], df_clientes, row['Tipo'], row['Fecha'])
                                st.download_button("📥 PDF", pdf_data, f"{row['Tipo']}_{i}.pdf", key=f"re_down_{i}", use_container_width=True)
                            elif row['Tipo'] == "PAGO":
                                # Re-construimos el desglose para el PDF si el pago histórico fue compuesto
                                split_detalles = row['Detalle'].split(" // ")
                                items_fake_pago = []
                                for det in split_detalles:
                                    items_fake_pago.append({
                                        "Producto": det, 
                                        "Cant": 1, 
                                        "Subtotal": row['Monto'] / len(split_detalles) # Distribución equitativa aproximada para el visor
                                    })
                                    
                                pdf_data_pago = generar_pdf_binario(cli_sel, items_fake_pago, row['Monto'], df_clientes, "RECIBO DE PAGO", row['Fecha'])
                                st.download_button("📥 RECIBO", pdf_data_pago, f"Recibo_{i}.pdf", key=f"re_down_pago_{i}", use_container_width=True)
                        
                        with col_del:
                            if st.button("🗑️ BORRAR", key=f"btn_pre_del_{i}", use_container_width=True):
                                st.session_state[f"confirmar_borrado_{i}"] = True

                        if st.session_state.get(f"confirmar_borrado_{i}", False):
                            st.markdown("---")
                            st.warning(f"⚠️ **¿Estás seguro de eliminar este movimiento de {formatear_moneda(row['Monto'])}?** Esta acción afectará el saldo actual del cliente y no se puede deshacer.")
                            
                            cb1, cb2 = st.columns(2)
                            with cb1:
                                if st.button("🔥 Sí, eliminar permanente", key=f"btn_del_conf_{i}", use_container_width=True):
                                    idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
                                    monto_mov = float(row['Monto'])
                                    
                                    if row['Tipo'] == "PAGO":
                                        df_clientes.at[idx_c, "Saldo"] += monto_mov
                                    elif row['Tipo'] == "VENTA":
                                        df_clientes.at[idx_c, "Saldo"] -= monto_mov
                                    elif row['Tipo'] == "N. CRÉDITO":
                                        df_clientes.at[idx_c, "Saldo"] += monto_mov
                                    
                                    df_movs = df_movs.drop(i)
                                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                                    df_movs.to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                                    
                                    st.session_state[f"confirmar_borrado_{i}"] = False
                                    st.success("Movimiento eliminado con éxito.")
                                    st.rerun()
                            
                            with cb2:
                                if st.button("❌ Cancelar", key=f"btn_del_canc_{i}", use_container_width=True):
                                    st.session_state[f"confirmar_borrado_{i}"] = False
                                    st.rerun()
            else:
                st.info("No hay movimientos registrados para este cliente.")

    with sub_gestion_clientes:
        st.subheader("Maestro de Clientes")
        
        with st.expander("➕ Agregar Nuevo Cliente"):
            with st.form("add_cli"):
                nc1, nc2 = st.columns(2)
                n_nom = nc1.text_input("Nombre Completo")
                n_tel = nc1.text_input("Teléfono")
                n_loc = nc2.text_input("Localidad")
                n_dir = nc2.text_input("Dirección")
                if st.form_submit_button("Guardar Cliente"):
                    if n_nom:
                        nuevo_c = pd.DataFrame([{"Nombre": n_nom, "Tel": n_tel, "Localidad": n_loc, "Direccion": n_dir, "Saldo": 0.0}])
                        df_clientes = pd.concat([df_clientes, nuevo_c], ignore_index=True)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        st.success("Cliente agregado"); st.rerun()

        st.markdown("---")
        st.write("**Listado de Clientes (Editar directamente en la tabla)**")
        df_cli_ed = st.data_editor(df_clientes, use_container_width=True, hide_index=True, key="ed_cli_tabla")
        
        c_btn1, c_btn2 = st.columns(2)
        if c_btn1.button("💾 Guardar Cambios en Tabla"):
            df_cli_ed.to_csv(ARCHIVO_CLIENTES, index=False)
            st.success("Cambios guardados"); st.rerun()
            
        if c_btn2.button("🗑️ Eliminar Cliente Seleccionado"):
            df_clientes = df_clientes[df_clientes["Nombre"] != cli_sel]
            df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
            st.error(f"Cliente {cli_sel} eliminado"); st.rerun()

with tabs[4]: # 📄 PRESUPUESTADOR (CON OPCIÓN DE IMPRESIÓN)
    st.header("📄 Generador de Documentos")
    
    cli_p = st.selectbox("Seleccionar Cliente:", 
                        df_clientes["Nombre"].tolist() if not df_clientes.empty else ["C. Final"], 
                        key="cli_presu_final_v2")
    
    p1, p2, p3 = st.columns([2, 1, 1])
    with p1: 
        i_p = st.selectbox("Articulo:", df_stock["Accesorio"].tolist(), key="item_presu_final_v2")
    with p2: 
        q_p = st.number_input("Cant:", min_value=1, value=1, key="cant_presu_final_v2")
    with p3: 
        l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_presu_final_v2")
    
    if st.button("➕ AGREGAR AL CARRITO", use_container_width=True):
        p_u = df_stock[df_stock["Accesorio"] == i_p][l_p].values[0]
        st.session_state.carrito.append({
            "Producto": i_p, 
            "Cant": q_p, 
            "Precio U.": p_u, 
            "Subtotal": p_u * q_p
        })
        st.rerun()

    if st.session_state.carrito:
        st.subheader("Artículos en el Presupuesto Actual")
        
        # Encabezados de la tabla visual
        eh1, eh2, eh3, eh4, eh5 = st.columns([3, 1, 1, 1, 0.5])
        eh1.markdown("**Artículo**")
        eh2.markdown("**Cant.**")
        eh3.markdown("**P. Unit**")
        eh4.markdown("**Subtotal**")
        eh5.markdown("") 
        
        # Dibujamos renglón por renglón con la cruz para borrar
        for idx, item in enumerate(st.session_state.carrito):
            with st.container(border=True):
                col_prod, col_cant, col_unit, col_sub, col_del = st.columns([3, 1, 1, 1, 0.5])
                
                col_prod.write(item["Producto"])
                col_cant.write(str(item["Cant"]))
                col_unit.write(formatear_moneda(item["Precio U."]))
                col_sub.write(formatear_moneda(item["Subtotal"]))
                
                # El botón de la cruz para sacar este accesorio específico
                if col_del.button("❌", key=f"quitar_item_v2_{idx}", help="Quitar este artículo"):
                    st.session_state.carrito.pop(idx)
                    st.rerun()
                    
        total_f = sum(item["Subtotal"] for item in st.session_state.carrito)
        st.write(f"### TOTAL: {formatear_moneda(total_f)}")
        
        st.markdown("---")
        st.subheader("Acciones de Documento")
        
        # Columnas para las acciones principales
        b1, b2, b3 = st.columns(3)
        
        with b1:
            # Opción 1: Solo Presupuesto (No afecta stock ni saldo)
            pdf_presu = generar_pdf_binario(cli_p, st.session_state.carrito, total_f, df_clientes, "PRESUPUESTO")
            st.download_button("📥 DESCARGAR PRESUPUESTO", pdf_presu, f"Presupuesto_{cli_p}.pdf", "application/pdf", use_container_width=True)
            if st.button("🗑️ LIMPIAR CARRITO", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()

        with b2:
            # Opción 2: Venta (Resta stock y suma saldo)
            if st.button("✅ GENERAR VENTA", use_container_width=True):
                for item in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                if cli_p != "C. Final":
                    df_clientes.loc[df_clientes["Nombre"] == cli_p, "Saldo"] += total_f
                
                # Guardar cambios
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                
                # Registrar en Movimientos
                detalles_venta = ", ".join([f"{i['Cant']}x {i['Producto']}" for i in st.session_state.carrito])
                n_v = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Cliente": cli_p,
                    "Tipo": "VENTA",
                    "Monto": total_f,
                    "Metodo": l_p,
                    "Detalle": detalles_venta[:100] # Limitar texto
                }])
                pd.concat([df_movs, n_v]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                
                st.session_state.confirmar_orden = True # Flag para mostrar descarga
                st.success("Venta procesada con éxito")

            if st.session_state.get('confirmar_orden', False):
                pdf_venta = generar_pdf_binario(cli_p, st.session_state.carrito, total_f, df_clientes, "ORDEN DE TRABAJO")
                st.download_button("🖨️ IMPRIMIR ORDEN", pdf_venta, f"Orden_{cli_p}.pdf", "application/pdf", use_container_width=True)
                if st.button("Cerrar Venta Actual"):
                    st.session_state.confirmar_orden = False
                    st.session_state.carrito = []
                    st.rerun()

        with b3:
            # Opción 3: Nota de Crédito (Suma stock y resta saldo)
            if st.button("🔵 GENERAR N. CRÉDITO", use_container_width=True):
                for item in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] += item["Cant"]
                if cli_p != "C. Final":
                    df_clientes.loc[df_clientes["Nombre"] == cli_p, "Saldo"] -= total_f
                
                # Guardar cambios
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                
                # Registrar en Movimientos
                detalles_nc = ", ".join([f"Dev: {i['Cant']}x {i['Producto']}" for i in st.session_state.carrito])
                n_nc = pd.DataFrame([{
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Cliente": cli_p,
                    "Tipo": "N. CRÉDITO",
                    "Monto": total_f,
                    "Metodo": "-",
                    "Detalle": detalles_nc[:100]
                }])
                pd.concat([df_movs, n_nc]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                
                st.session_state.confirmar_nc = True # Flag para mostrar descarga
                st.warning("Nota de Crédito processed")

            if st.session_state.get('confirmar_nc', False):
                pdf_nc = generar_pdf_binario(cli_p, st.session_state.carrito, total_f, df_clientes, "NOTA DE CRÉDITO")
                st.download_button("🖨️ IMPRIMIR N.C.", pdf_nc, f"NC_{cli_p}.pdf", "application/pdf", use_container_width=True)
                if st.button("Cerrar N.C. Actual"):
                    st.session_state.confirmar_nc = False
                    st.session_state.carrito = []
                    st.rerun()

with tabs[5]: # ÓRDENES
    st.header("📋 Historial Global")
    st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)

with tabs[6]: # 🏁 CIERRE (FINANZAS Y CAPITAL)
    st.header("🏁 Cierre y Balance General")
    
    # Cálculos de Capital
    # 1. Invertido: Suma de (Costo Base + Flete) * Cantidad cargada históricamente 
    # (En este caso lo calculamos como el valor de reposición de lo que hay + ventas registradas si tuvieras histórico de costos)
    capital_en_stock = (df_stock["Costo Base"] * df_stock["Stock"]).sum()
    capital_flete = (df_stock["Flete"] * df_stock["Stock"]).sum()
    total_invertido_actual = capital_en_stock + capital_flete
    
    # 2. Por Cobrar: Suma de saldos de clientes
    total_por_cobrar = df_clientes["Saldo"].sum()
    
    # 3. Valor de Venta Estimado: Lo que valdría el stock a precio de lista 2
    valor_venta_stock = (df_stock["Lista 2 (Efectivo)"] * df_stock["Stock"]).sum()

    # --- TABLERO DE MÉTRICAS PRINCIPALES ---
    st.subheader("Estado Patrimonial")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.metric(
            label="📦 En Stock (Costo)", 
            value=formatear_moneda(total_invertido_actual),
            help="Suma de Costo Base + Flete de todos los productos en inventario."
        )
        
    with c2:
        st.metric(
            label="👥 Por Cobrar", 
            value=formatear_moneda(total_por_cobrar),
            help="Suma total de las cuentas corrientes de todos los clientes."
        )
        
    with c3:
        capital_total = total_invertido_actual + total_por_cobrar
        st.metric(
            label="💰 Capital Total", 
            value=formatear_moneda(capital_total),
            delta=f"Proyección Venta: {formatear_moneda(valor_venta_stock)}",
            help="Suma de mercadería a costo + deudas de clientes."
        )

    st.markdown("---")

    # --- DESGLOSE POR RUBRO O PROVEEDOR ---
    col_inf1, col_inf2 = st.columns(2)
    
    with col_inf1:
        st.subheader("Inversión por Rubro")
        resumen_rubro = df_stock.groupby("Rubro").apply(
            lambda x: (x["Costo Base"] * x["Stock"]).sum()
        ).reset_index()
        resumen_rubro.columns = ["Rubro", "Inversión ($)"]
        st.dataframe(resumen_rubro, use_container_width=True, hide_index=True)

    with col_inf2:
        st.subheader("Mayores Deudores")
        deudores = df_clientes[df_clientes["Saldo"] > 0][["Nombre", "Saldo"]].sort_values(by="Saldo", ascending=False)
        st.dataframe(deudores, use_container_width=True, hide_index=True)

    # --- CIERRE DE CAJA DIARIO (OPCIONAL) ---
    st.markdown("---")
    st.subheader("💵 Resumen de Movimientos Hoy")
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    movs_hoy = df_movs[df_movs["Fecha"].str.contains(fecha_hoy)]
    
    if not movs_hoy.empty:
        total_ingresos_hoy = movs_hoy[movs_hoy["Tipo"] == "PAGO"]["Monto"].sum()
        st.info(f"Efectivo/Pagos ingresados hoy: **{formatear_moneda(total_ingresos_hoy)}**")
        st.dataframe(movs_hoy, use_container_width=True, hide_index=True)
    else:
        st.write("No se registraron movimientos de caja en el día de la fecha.")

with tabs[7]: # 📦 REMITOS (ESTILO PRESUPUESTADOR)
    st.header("📦 Generador de Remitos")
    
    # 1. Selección de Cliente
    cli_r = st.selectbox(
        "Seleccionar Cliente para el Remito:", 
        df_clientes["Nombre"].tolist() if not df_clientes.empty else ["C. Final"], 
        key="cli_remito_final"
    )
    
    # 2. Selección de Productos (Igual a presupuestos pero sin elección de Lista)
    r1, r2 = st.columns([3, 1])
    with r1:
        i_r = st.selectbox("Articulo para el Remito:", df_stock["Accesorio"].tolist(), key="item_remito_final")
    with r2:
        q_r = st.number_input("Cantidad:", min_value=1, value=1, key="cant_remito_final")
    
    if st.button("➕ AGREGAR AL REMITO", use_container_width=True):
        # En el remito solo nos interesa Producto y Cantidad
        st.session_state.remito_items.append({
            "Producto": i_r,
            "Cant": q_r,
            "Precio U.": 0, # No se muestra en remito
            "Subtotal": 0   # No se muestra en remito
        })
        st.rerun()

    # 3. Visualización y Descarga
    if st.session_state.remito_items:
        st.subheader("Items en el Remito Actual")
        # Mostrar tabla simple
        df_remito_vista = pd.DataFrame(st.session_state.remito_items)[["Producto", "Cant"]]
        st.table(df_remito_vista)
        
        st.markdown("---")
        rd1, rd2 = st.columns(2)
        
        with rd1:
            # Generar PDF (Usamos el título REMITO para que la función PDF oculte los precios)
            pdf_remito = generar_pdf_binario(
                cli_r, 
                st.session_state.remito_items, 
                0, 
                df_clientes, 
                titulo="REMITO DE ENTREGA"
            )
            st.download_button(
                label="📥 DESCARGAR REMITO",
                data=pdf_remito,
                file_name=f"Remito_{cli_r}_{datetime.now().strftime('%d_%m')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        with rd2:
            if st.button("🗑️ LIMPIAR REMITO", use_container_width=True):
                st.session_state.remito_items = []
                st.rerun()
                
        st.info("Nota: El remito no afecta saldos de cuenta corriente ni stock automáticamente (usar la pestaña de Ventas para eso).")
