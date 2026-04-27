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
        pdf = PDF() 
        pdf.add_page()
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dir = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"
        fecha_display = fecha_fija if fecha_fija else datetime.now().strftime('%d/%m/%Y %H:%M')

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {titulo}", ln=True, fill=True, border=1)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(95, 7, f" CLIENTE: {cliente_nombre}", border="LT")
        pdf.cell(95, 7, f" FECHA: {fecha_display}", border="RT", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, f" TEL: {tel}", border="L")
        pdf.cell(95, 7, f" LOCALIDAD: {loc}", border="R", ln=True)
        pdf.cell(190, 7, f" DIRECCION: {dir}", border="LRB", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(200, 200, 200)
        pdf.cell(100, 10, " Articulo", border=1, fill=True)
        pdf.cell(20, 10, "Cant.", border=1, fill=True, align="C")
        pdf.cell(35, 10, "P. Unit", border=1, fill=True, align="R")
        pdf.cell(35, 10, "Subtotal", border=1, fill=True, align="R", ln=True)
        
        pdf.set_font("Helvetica", "", 10)
        for item in carrito:
            pdf.cell(100, 8, f" {item['Producto']}", border=1)
            pdf.cell(20, 8, str(item['Cant']), border=1, align="C")
            pdf.cell(35, 8, f"{formatear_moneda(item['Precio U.'])} ", border=1, align="R")
            pdf.cell(35, 8, f"{formatear_moneda(item['Subtotal'])} ", border=1, align="R", ln=True)
        
        pdf.ln(2); pdf.set_font("Helvetica", "B", 12)
        pdf.cell(155, 10, "TOTAL:", border=0, align="R")
        pdf.cell(35, 10, f"{formatear_moneda(total)}", border=1, align="R")
        
        res = pdf.output(dest='S')
        if isinstance(res, str): return res.encode('latin-1', 'replace')
        return bytes(res)
    except Exception as e:
        st.error(f"Error PDF: {str(e)}")
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
            if nuevo_costo > 0:
                df_stock.at[idx, "Costo Base"] = nuevo_costo
                flete = df_stock.at[idx, "Flete"]
                ganancia = df_stock.at[idx, "% Ganancia"]
                l1 = (nuevo_costo + flete) * (1 + ganancia / 100)
                df_stock.at[idx, "Lista 1 (Cheques)"] = round(l1, 2)
                df_stock.at[idx, "Lista 2 (Efectivo)"] = round(l1 * 0.90, 2)
            
            df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
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
                    st.success(f"Producto {n_acc} creado.")
                    st.rerun()
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

            # --- SECCIÓN DE PAGOS ---
            st.subheader("Registrar Pago")
            with st.expander("Formulario de Pago"):
                with st.form("form_pago"):
                    f1, f2, f3 = st.columns(3)
                    with f1:
                        monto_p = st.number_input("Monto $:", min_value=0.0, format="%.2f")
                    with f2:
                        forma_p = st.selectbox("Forma de Pago:", ["Efectivo", "Transferencia", "Cheque", "Echeq"])
                    with f3:
                        fecha_p = st.date_input("Fecha de cobro:", datetime.now())
                    
                    detalles_p = ""
                    if forma_p in ["Cheque", "Echeq"]:
                        st.markdown("**Detalles del Título:**")
                        d1, d2, d3 = st.columns(3)
                        n_cheque = d1.text_input("Número de Cheque")
                        b_cheque = d2.text_input("Banco")
                        v_cheque = d3.date_input("Vencimiento")
                        detalles_p = f"{forma_p} N°{n_cheque} - {b_cheque} (Vto: {v_cheque})"
                    else:
                        detalles_p = st.text_input("Nota adicional (opcional):")

                    if st.form_submit_button("Confirmar y Descargar Recibo"):
                        # Actualizar Saldo
                        df_clientes.at[idx_c, "Saldo"] -= monto_p
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        
                        # Registrar Movimiento
                        n_mov = pd.DataFrame([{
                            "Fecha": fecha_p.strftime("%d/%m/%Y"),
                            "Cliente": cli_sel,
                            "Tipo": "PAGO",
                            "Monto": monto_p,
                            "Metodo": forma_p,
                            "Detalle": detalles_p
                        }])
                        df_movs = pd.concat([df_movs, n_mov], ignore_index=True)
                        df_movs.to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                        
                        st.success(f"Pago registrado para {cli_sel}")
                        st.rerun()

            # --- HISTORIAL ESPECÍFICO Y RE-DESCARGA ---
            st.subheader(f"Movimientos de {cli_sel}")
            historial_cli = df_movs[df_movs["Cliente"] == cli_sel].sort_index(ascending=False)
            
            if not historial_cli.empty:
                for i, row in historial_cli.iterrows():
                    with st.container(border=True):
                        col_info, col_btn = st.columns([4, 1])
                        with col_info:
                            st.write(f"**{row['Fecha']}** | {row['Tipo']} | **{formatear_moneda(row['Monto'])}**")
                            st.caption(f"Método: {row['Metodo']} | Detalle: {row['Detalle']}")
                        
                        with col_btn:
                            # Lógica de re-descarga según el tipo de movimiento
                            if row['Tipo'] in ["VENTA", "N. CRÉDITO"]:
                                # Simulamos los items para el PDF (puedes ajustar esto si guardas los carritos en archivos)
                                items_fake = [{"Producto": row['Detalle'], "Cant": 1, "Precio U.": row['Monto'], "Subtotal": row['Monto']}]
                                pdf_data = generar_pdf_binario(cli_sel, items_fake, row['Monto'], df_clientes, row['Tipo'], row['Fecha'])
                                st.download_button("📥 PDF", pdf_data, f"{row['Tipo']}_{i}.pdf", key=f"re_down_{i}")
            else:
                st.info("No hay movimientos registrados para este cliente.")

    with sub_gestion_clientes:
        st.subheader("Maestro de Clientes")
        
        # 1. Agregar Cliente
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

        # 2. Modificar/Eliminar Cliente
        st.markdown("---")
        st.write("**Listado de Clientes (Editar directamente en la tabla)**")
        df_cli_ed = st.data_editor(df_clientes, use_container_width=True, hide_index=True, key="ed_cli_tabla")
        
        c_btn1, c_btn2 = st.columns(2)
        if c_btn1.button("💾 Guardar Cambios en Tabla"):
            df_cli_ed.to_csv(ARCHIVO_CLIENTES, index=False)
            st.success("Cambios guardados"); st.rerun()
            
        if c_btn2.button("🗑️ Eliminar Cliente Seleccionado"):
            # Lógica para eliminar el que esté seleccionado en el selectbox de arriba
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
        st.table(st.session_state.carrito)
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
                st.warning("Nota de Crédito procesada")

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
