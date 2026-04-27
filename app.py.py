import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# --- RUTAS DE ARCHIVOS ---
if not os.path.exists("data"):
    os.makedirs("data")

ARCHIVO_ARTICULOS = "data/lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "data/clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "data/movimientos_clientes.csv"
ARCHIVO_HISTORIAL_STOCK = "data/historial_stock.csv"
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
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Lista", "Costo", "Flete", "Stock", "%"]) else ""
            return df[columns]
        except:
            return pd.DataFrame(columns=columns)
    return pd.DataFrame(columns=columns)

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]
COLS_HISTORIAL_STOCK = ["Fecha", "Accesorio", "Cantidad", "Tipo Operacion", "Proveedor"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)
df_hist_stock = cargar_datos(ARCHIVO_HISTORIAL_STOCK, COLS_HISTORIAL_STOCK)

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

def generar_pdf(cliente_nombre, items, total, df_clientes, titulo="DOCUMENTO"):
    try:
        pdf = PDF()
        pdf.add_page()
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f" {titulo}", ln=True, fill=True, border=1)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"CLIENTE: {cliente_nombre}", ln=True)
        pdf.cell(0, 7, f"LOCALIDAD: {loc} | TEL: {tel}", ln=True)
        pdf.cell(0, 7, f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.ln(5)
        
        # Tabla
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(100, 8, "Producto", 1)
        pdf.cell(20, 8, "Cant", 1, align="C")
        pdf.cell(35, 8, "P. Unit", 1, align="R")
        pdf.cell(35, 8, "Subtotal", 1, align="R", ln=True)
        
        pdf.set_font("Helvetica", "", 10)
        for item in items:
            pdf.cell(100, 8, f" {item['Producto'][:45]}", 1)
            pdf.cell(20, 8, str(item['Cant']), 1, align="C")
            pdf.cell(35, 8, formatear_moneda(item['Precio U.']), 1, align="R")
            pdf.cell(35, 8, formatear_moneda(item['Subtotal']), 1, align="R", ln=True)
            
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(155, 10, "TOTAL: ", 0, align="R")
        pdf.cell(35, 10, formatear_moneda(total), 1, align="R")
        
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        st.error(f"Error generando PDF: {e}")
        return b""

# --- INTERFAZ PRINCIPAL ---
tabs = st.tabs(["📊 Stock", "🚚 Lote/Carga", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre", "📦 Remitos"])

# --- TAB 0: STOCK ---
with tabs[0]:
    st.header("Inventario Actual")
    if not df_stock.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Costo Total Stock", formatear_moneda((df_stock['Costo Base'] * df_stock['Stock']).sum()))
        c2.metric("Valor Lista 1", formatear_moneda((df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()))
        c3.metric("Valor Lista 2", formatear_moneda((df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()))
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

# --- TAB 1: LOTE / CARGA ---
with tabs[1]:
    st.header("🚚 Gestión de Ingresos")
    sub_lote = st.tabs(["➕ Agregar / Modificar", "📜 Historial de Carga"])
    
    with sub_lote[0]:
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            st.subheader("Cargar Producto Existente")
            prod_ex = st.selectbox("Seleccionar Accesorio:", df_stock["Accesorio"].tolist() if not df_stock.empty else ["No hay productos"])
            cant_ex = st.number_input("Cantidad a sumar:", min_value=1, value=1)
            if st.button("Actualizar Stock Existente"):
                df_stock.loc[df_stock["Accesorio"] == prod_ex, "Stock"] += cant_ex
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                # Historial
                nuevo_hist = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Accesorio": prod_ex, "Cantidad": cant_ex, "Tipo Operacion": "REPOSICIÓN", "Proveedor": "-"}])
                pd.concat([df_hist_stock, nuevo_hist]).to_csv(ARCHIVO_HISTORIAL_STOCK, index=False)
                st.success("Stock actualizado correctamente"); st.rerun()

        with col_l2:
            st.subheader("Cargar Nuevo Producto")
            with st.form("nuevo_prod_lote"):
                n_rubro = st.text_input("Rubro")
                n_prov = st.text_input("Proveedor")
                n_acc = st.text_input("Nombre Accesorio")
                n_stock = st.number_input("Stock Inicial", min_value=0)
                n_costo = st.number_input("Costo Base", min_value=0.0)
                n_flete = st.number_input("Flete", min_value=0.0)
                n_gan = st.number_input("% Ganancia", min_value=0.0, value=30.0)
                if st.form_submit_button("Incorporar al Maestro"):
                    l1 = round((n_costo + n_flete) * (1 + n_gan/100), 2)
                    l2 = round(l1 * 0.9, 2)
                    nuevo_item = pd.DataFrame([{"Rubro": n_rubro, "Proveedor": n_prov, "Accesorio": n_acc, "Stock": n_stock, "Costo Base": n_costo, "Flete": n_flete, "% Ganancia": n_gan, "Lista 1 (Cheques)": l1, "Lista 2 (Efectivo)": l2, "Descripcion": ""}])
                    pd.concat([df_stock, nuevo_item]).to_csv(ARCHIVO_ARTICULOS, index=False)
                    # Historial
                    nuevo_hist = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Accesorio": n_acc, "Cantidad": n_stock, "Tipo Operacion": "ALTA NUEVA", "Proveedor": n_prov}])
                    pd.concat([df_hist_stock, nuevo_hist]).to_csv(ARCHIVO_HISTORIAL_STOCK, index=False)
                    st.success("Producto creado e incorporado"); st.rerun()

    with sub_lote[1]:
        st.subheader("Historial de movimientos de Stock")
        st.dataframe(df_hist_stock.sort_index(ascending=False), use_container_width=True)

# --- TAB 2: MAESTRO ---
with tabs[2]:
    st.header("⚙️ Edición Maestra")
    df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
    if st.button("Guardar Cambios"):
        df_ed["Lista 1 (Cheques)"] = ((df_ed["Costo Base"] + df_ed["Flete"]) * (1 + df_ed["% Ganancia"] / 100)).round(2)
        df_ed["Lista 2 (Efectivo)"] = (df_ed["Lista 1 (Cheques)"] * 0.9).round(2)
        df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
        st.success("Base actualizada"); st.rerun()

# --- TAB 3: CTA CTE ---
with tabs[3]:
    st.header("👥 Gestión de Cuentas Corrientes")
    sub_cta = st.tabs(["💰 Pagos y Saldos", "🛠️ Administrar Clientes"])
    
    with sub_cta[0]:
        if not df_clientes.empty:
            cli_sel = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="cli_pago")
            idx_cli = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
            st.metric("Saldo Actual", formatear_moneda(df_clientes.at[idx_cli, "Saldo"]))
            
            with st.expander("Registrar Nuevo Pago"):
                monto_p = st.number_input("Monto a pagar $:", min_value=0.0)
                metodo_p = st.selectbox("Método de Pago:", ["Efectivo", "Transferencia", "Cheque Físico", "eCheq"])
                det_pago = ""
                if "Cheque" in metodo_p or "eCheq" in metodo_p:
                    c_num = st.text_input("Número de Cheque")
                    c_banco = st.text_input("Banco")
                    c_vence = st.date_input("Fecha de Vencimiento")
                    det_pago = f"{metodo_p} N°{c_num} - {c_banco} (Vto: {c_vence})"
                else:
                    det_pago = f"Pago en {metodo_p}"
                
                if st.button("Confirmar Pago"):
                    df_clientes.at[idx_cli, "Saldo"] = round(df_clientes.at[idx_cli, "Saldo"] - monto_p, 2)
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_sel, "Tipo": "PAGO", "Monto": monto_p, "Metodo": metodo_p, "Detalle": det_pago}])
                    pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.success("Pago registrado"); st.rerun()
        else:
            st.info("No hay clientes cargados.")

    with sub_cta[1]:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.subheader("Nuevo Cliente")
            with st.form("f_nuevo_cli"):
                nc_nom = st.text_input("Nombre Completo")
                nc_tel = st.text_input("Teléfono")
                nc_loc = st.text_input("Localidad")
                nc_dir = st.text_input("Dirección")
                if st.form_submit_button("Guardar Cliente"):
                    n_cli = pd.DataFrame([{"Nombre": nc_nom, "Tel": nc_tel, "Localidad": nc_loc, "Direccion": nc_dir, "Saldo": 0.0}])
                    pd.concat([df_clientes, n_cli]).to_csv(ARCHIVO_CLIENTES, index=False)
                    st.success("Cliente guardado"); st.rerun()
        with col_c2:
            st.subheader("Modificar / Eliminar")
            if not df_clientes.empty:
                cli_mod = st.selectbox("Cliente a editar:", df_clientes["Nombre"].tolist())
                if st.button("🗑️ Eliminar Cliente"):
                    df_clientes = df_clientes[df_clientes["Nombre"] != cli_mod]
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    st.error("Cliente eliminado"); st.rerun()

# --- TAB 4: PRESUPUESTADOR ---
with tabs[4]:
    st.header("📄 Presupuestador")
    cli_pres = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_pres")
    
    col_p1, col_p2, col_p3 = st.columns([2,1,1])
    with col_p1: item_p = st.selectbox("Producto:", df_stock["Accesorio"].tolist())
    with col_p2: cant_p = st.number_input("Cantidad:", min_value=1, value=1, key="cant_p")
    with col_p3: lista_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
    
    if st.button("➕ Agregar al Carrito"):
        precio = df_stock[df_stock["Accesorio"] == item_p][lista_p].values[0]
        st.session_state.carrito.append({"Producto": item_p, "Cant": cant_p, "Precio U.": precio, "Subtotal": round(precio * cant_p, 2)})
        st.rerun()

    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        t_final = round(sum(i["Subtotal"] for i in st.session_state.carrito), 2)
        st.subheader(f"Total: {formatear_moneda(t_final)}")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pdf_data = generar_pdf(cli_pres, st.session_state.carrito, t_final, df_clientes, "PRESUPUESTO")
            st.download_button("📥 Descargar PDF", pdf_data, f"Presupuesto_{cli_pres}.pdf", "application/pdf")
        with c2:
            if st.button("✅ Generar Orden"): st.session_state.confirmar_orden = True
        with c3:
            if st.button("🔵 Nota de Crédito"): st.session_state.confirmar_nc = True
        with c4:
            if st.button("🗑️ Limpiar"): st.session_state.carrito = []; st.rerun()

        if st.session_state.confirmar_orden:
            st.warning(f"¿Confirmar Orden para {cli_pres}?")
            if st.button("SÍ, CONFIRMAR ORDEN"):
                for item in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                if cli_pres != "Consumidor Final":
                    df_clientes.loc[df_clientes["Nombre"] == cli_pres, "Saldo"] += t_final
                
                det = ", ".join([f"{i['Cant']}x {i['Producto']}" for i in st.session_state.carrito])
                n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_pres, "Tipo": "VENTA", "Monto": t_final, "Metodo": "-", "Detalle": det}])
                
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                st.session_state.carrito = []; st.session_state.confirmar_orden = False; st.success("Orden procesada"); st.rerun()

        if st.session_state.confirmar_nc:
            st.error(f"¿Confirmar Nota de Crédito (Devolución) para {cli_pres}?")
            if st.button("SÍ, EMITIR NC"):
                for item in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] += item["Cant"]
                if cli_pres != "Consumidor Final":
                    df_clientes.loc[df_clientes["Nombre"] == cli_pres, "Saldo"] -= t_final
                
                n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_pres, "Tipo": "N. CRÉDITO", "Monto": t_final, "Metodo": "-", "Detalle": "Devolución de productos"}])
                
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                st.session_state.carrito = []; st.session_state.confirmar_nc = False; st.success("NC Procesada"); st.rerun()

# --- TAB 5: ÓRDENES ---
with tabs[5]:
    st.header("📋 Historial de Movimientos")
    st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True, hide_index=True)

# --- TAB 6: CIERRE ---
with tabs[6]:
    st.header("🏁 Cierre de Caja y Estado")
    c1, c2, c3 = st.columns(3)
    c1.metric("Deuda Total Clientes", formatear_moneda(df_clientes['Saldo'].sum()))
    c2.metric("Ventas del Mes", formatear_moneda(df_movs[df_movs["Tipo"]=="VENTA"]["Monto"].sum()))
    c3.metric("Pagos Recibidos", formatear_moneda(df_movs[df_movs["Tipo"]=="PAGO"]["Monto"].sum()))
    
    st.subheader("Últimos Pagos con Cheque")
    cheques = df_movs[df_movs["Metodo"].str.contains("Cheque|eCheq", na=False)]
    st.dataframe(cheques, use_container_width=True)

# --- TAB 7: REMITOS ---
with tabs[7]:
    st.header("📦 Generador de Remitos")
    cli_rem = st.selectbox("Cliente para Remito:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
    r1, r2 = st.columns([3, 1])
    with r1: item_r = st.selectbox("Producto a enviar:", df_stock["Accesorio"].tolist(), key="item_r")
    with r2: cant_r = st.number_input("Cant:", min_value=1, value=1, key="cant_r")
    
    if st.button("Agregar al Remito"):
        st.session_state.remito_items.append({"Producto": item_r, "Cant": cant_r, "Precio U.": 0.0, "Subtotal": 0.0})
        st.rerun()
    
    if st.session_state.remito_items:
        st.write("Artículos en remito:")
        st.table(st.session_state.remito_items)
        if st.button("Descargar Remito PDF"):
            pdf_rem = generar_pdf(cli_rem, st.session_state.remito_items, 0, df_clientes, "REMITO DE ENTREGA")
            st.download_button("📥 Bajar Remito", pdf_rem, f"Remito_{cli_rem}.pdf", "application/pdf")
        if st.button("Limpiar Remito"):
            st.session_state.remito_items = []; st.rerun()
