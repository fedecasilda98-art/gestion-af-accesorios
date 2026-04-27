import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# --- RUTAS DE ARCHIVOS ---
if not os.path.exists("data"):
    os.makedirs("data")

ARCHIVO_ARTICULOS = "data/lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "data/clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "data/movimientos_clientes.csv"
ARCHIVO_HISTORIAL_STOCK = "data/historial_stock.csv"

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
if "pdf_a_descargar" not in st.session_state: st.session_state.pdf_a_descargar = None

# --- UTILIDADES ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- CLASE PDF REDISEÑADA ---
class PDF(FPDF):
    def header(self):
        # Título principal a la izquierda
        self.set_font("Helvetica", "B", 18)
        self.cell(100, 10, "AF ACCESORIOS - ALUMINIO", 0, 0, "L")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 10, "ACCESORIOS DE ALUMINIO", 0, 1, "R")
        
        self.set_font("Helvetica", "", 10)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", 0, 1, "L")
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

def generar_pdf(cliente_nombre, items, total, df_clientes, titulo="PRESUPUESTO"):
    try:
        pdf = PDF()
        pdf.add_page()
        
        info_cli = df_clientes[df_clientes["Nombre"] == cliente_nombre]
        tel = str(info_cli["Tel"].values[0]) if not info_cli.empty else "-"
        loc = str(info_cli["Localidad"].values[0]) if not info_cli.empty else "-"
        dir_cli = str(info_cli["Direccion"].values[0]) if not info_cli.empty else "-"
        
        # Tipo de documento
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f"TIPO DE DOCUMENTO: {titulo}", 0, 1, "L")
        pdf.ln(2)
        
        # Info Cliente
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 7, "CLIENTE:", 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(70, 7, f"{cliente_nombre}", 0, 0)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 7, "FECHA:", 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"{datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 7, "DIRECCIÓN:", 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(70, 7, f"{dir_cli}", 0, 0)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 7, "LOCALIDAD:", 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"{loc}", 0, 1)

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 7, "TEL:", 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"{tel}", 0, 1)
        
        pdf.ln(10)
        
        # Tabla de Artículos
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(100, 8, " Artículo / Accesorio", 1, 0, "L", True)
        pdf.cell(20, 8, "Cant.", 1, 0, "C", True)
        pdf.cell(35, 8, "P. Unit", 1, 0, "C", True)
        pdf.cell(35, 8, "Subtotal", 1, 1, "C", True)
        
        pdf.set_font("Helvetica", "", 10)
        for item in items:
            prod_nom = str(item['Producto'])[:45].encode('latin-1', 'ignore').decode('latin-1')
            pdf.cell(100, 8, f" {prod_nom}", 1)
            pdf.cell(20, 8, str(item['Cant']), 1, 0, "C")
            pdf.cell(35, 8, formatear_moneda(item['Precio U.']), 1, 0, "R")
            pdf.cell(35, 8, formatear_moneda(item['Subtotal']), 1, 1, "R")
            
        # Total
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(120, 10, "", 0, 0)
        pdf.cell(35, 10, "TOTAL:", 1, 0, "C", True)
        pdf.cell(35, 10, formatear_moneda(total), 1, 1, "R")
        
        resultado = pdf.output(dest='S')
        return bytes(resultado) if not isinstance(resultado, str) else resultado.encode('latin-1')
    except Exception as e:
        st.error(f"Error generando PDF: {e}")
        return None

# --- PESTAÑAS ---
tabs = st.tabs(["📊 Stock", "🚚 Lote/Carga", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre", "📦 Remitos", "📂 Importar"])

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

with tabs[4]:
    st.header("📄 Presupuestador y Ventas")
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
            pdf_pres = generar_pdf(cli_pres, st.session_state.carrito, t_final, df_clientes, "PRESUPUESTO")
            if pdf_pres:
                st.download_button("📥 Bajar Presupuesto", pdf_pres, f"Presupuesto_{cli_pres}.pdf", "application/pdf")
        with c2:
            if st.button("✅ Generar Orden"): st.session_state.confirmar_orden = True
        with c3:
            if st.button("🔵 Nota de Crédito"): st.session_state.confirmar_nc = True
        with c4:
            if st.button("🗑️ Limpiar"): 
                st.session_state.carrito = []; st.session_state.pdf_a_descargar = None; st.rerun()

        if st.session_state.confirmar_orden:
            if st.button("SÍ, CONFIRMAR ORDEN"):
                for item in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                if cli_pres != "Consumidor Final":
                    df_clientes.loc[df_clientes["Nombre"] == cli_pres, "Saldo"] += t_final
                
                # Generar PDF con nuevo diseño
                st.session_state.pdf_a_descargar = generar_pdf(cli_pres, st.session_state.carrito, t_final, df_clientes, "ORDEN DE VENTA")
                
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                st.session_state.carrito = []
                st.session_state.confirmar_orden = False
                st.success("Orden procesada")
                st.rerun()

        if st.session_state.pdf_a_descargar:
            st.download_button("📥 DESCARGAR COMPROBANTE", st.session_state.pdf_a_descargar, f"Comprobante_{cli_pres}.pdf", "application/pdf")

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

with tabs[7]:
    st.header("📦 Generador de Remitos")
    cli_rem = st.selectbox("Cliente para Remito:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_rem_box")
    # ... (resto de lógica de remito usa generar_pdf con el nuevo diseño)
    if st.button("Generar Remito PDF"):
        pdf_rem = generar_pdf(cli_rem, st.session_state.remito_items, 0, df_clientes, "REMITO DE ENTREGA")
        if pdf_rem:
            st.download_button("📥 BAJAR REMITO", pdf_rem, f"Remito_{cli_rem}.pdf", "application/pdf")

# --- TAB 8: IMPORTAR ---
with tabs[8]:
    st.header("📂 Importación Masiva de Datos")
    tipo_import = st.radio("¿Qué deseas importar?", ["Artículos (Maestro)", "Clientes"])
    file_upload = st.file_uploader("Subir CSV", type=["csv"])
    if file_upload is not None:
        if st.button("Procesar Importación"):
            new_data = pd.read_csv(file_upload)
            if tipo_import == "Artículos (Maestro)":
                new_data.to_csv(ARCHIVO_ARTICULOS, index=False)
            else:
                new_data.to_csv(ARCHIVO_CLIENTES, index=False)
            st.success("Importación exitosa.")
            st.rerun()
