import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios", layout="wide")

if not os.path.exists("data"):
    os.makedirs("data")

# Rutas y Columnas (Unificadas para evitar NameError)
ARCHIVOS = {
    "articulos": "data/lista_articulos_interna.csv",
    "clientes": "data/clientes_base.csv",
    "movs": "data/movimientos_clientes.csv",
    "hist_stock": "data/historial_stock.csv"
}

COLS_ARTICULOS = ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"]
COLS_CLIENTES = ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"]
COLS_MOVS = ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"]
COLS_HIST_STOCK = ["Fecha", "Accesorio", "Cantidad", "Tipo Operacion", "Proveedor"]

def cargar_datos(tipo, columnas):
    ruta = ARCHIVOS[tipo]
    if os.path.exists(ruta):
        try:
            df = pd.read_csv(ruta)
            for c in columnas:
                if c not in df.columns: df[c] = 0.0 if any(x in c for x in ["Saldo", "Monto", "Lista"]) else ""
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos("articulos", COLS_ARTICULOS)
df_clientes = cargar_datos("clientes", COLS_CLIENTES)
df_movs = cargar_datos("movs", COLS_MOVS)
df_hist_stock = cargar_datos("hist_stock", COLS_HIST_STOCK)

if "carrito" not in st.session_state: st.session_state.carrito = []
if "remito_items" not in st.session_state: st.session_state.remito_items = []

# --- CORRECCIÓN PDF (SOLUCIÓN AL ERROR DE IMPRESIÓN) ---
def generar_pdf_corregido(cliente, items, total, titulo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "AF ACCESORIOS - Casilda", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"{titulo} | Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, f"CLIENTE: {cliente}", ln=True)
    
    # Tabla
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(90, 8, "Producto", 1, 0, 'L', True)
    pdf.cell(20, 8, "Cant", 1, 0, 'C', True)
    pdf.cell(40, 8, "P. Unit", 1, 0, 'R', True)
    pdf.cell(40, 8, "Subtotal", 1, 1, 'R', True)
    
    pdf.set_font("Arial", "", 10)
    for i in items:
        pdf.cell(90, 8, str(i['Producto'])[:45], 1)
        pdf.cell(20, 8, str(i['Cant']), 1, align='C')
        pdf.cell(40, 8, f"$ {i['Precio U.']:,.2f}", 1, align='R')
        pdf.cell(40, 8, f"$ {i['Subtotal']:,.2f}", 1, 1, align='R')
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(150, 10, "TOTAL: ", 0, 0, 'R')
    pdf.cell(40, 10, f"$ {total:,.2f}", 1, 1, 'R')
    
    # Retornar como bytes para evitar errores de codificación
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "👥 Cta Cte", "📄 Presupuestador", "📋 Movimientos", "🏁 Cierre", "📦 Remitos", "⚙️ Maestro"])

# TAB LOTE (Con Historial y Selección)
with tabs[1]:
    st.header("Gestión de Lotes")
    sub_l1, sub_l2 = st.tabs(["Carga de Stock", "📜 Historial de Cargas"])
    with sub_l1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Productos Cargados")
            p_ex = st.selectbox("Elegir producto:", df_stock["Accesorio"].tolist(), key="p_lote_ex")
            c_ex = st.number_input("Cantidad a sumar:", min_value=1, key="c_lote_ex")
            if st.button("Actualizar Stock"):
                df_stock.loc[df_stock["Accesorio"] == p_ex, "Stock"] += c_ex
                df_stock.to_csv(ARCHIVOS["articulos"], index=False)
                new_h = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Accesorio": p_ex, "Cantidad": c_ex, "Tipo Operacion": "REPOSICION", "Proveedor": "-"}])
                pd.concat([df_hist_stock, new_h]).to_csv(ARCHIVOS["hist_stock"], index=False)
                st.success("Stock sumado"); st.rerun()
        with c2:
            st.subheader("Nuevo Producto")
            with st.form("nuevo_p"):
                n_acc = st.text_input("Nombre")
                n_cos = st.number_input("Costo Base", min_value=0.0)
                n_stk = st.number_input("Stock Inicial", min_value=0)
                if st.form_submit_button("Dar de Alta"):
                    l1 = n_cos * 1.3
                    n_row = pd.DataFrame([{"Rubro": "-", "Proveedor": "-", "Accesorio": n_acc, "Stock": n_stk, "Costo Base": n_cos, "Flete": 0, "% Ganancia": 30, "Lista 1 (Cheques)": l1, "Lista 2 (Efectivo)": l1*0.9, "Descripcion": ""}])
                    pd.concat([df_stock, n_row]).to_csv(ARCHIVOS["articulos"], index=False)
                    st.success("Alta exitosa"); st.rerun()
    with sub_l2:
        st.dataframe(df_hist_stock.sort_index(ascending=False), use_container_width=True)

# TAB CTA CTE (Gestión de Clientes y Pagos Detallados)
with tabs[2]:
    st.header("Cuentas Corrientes")
    s_c1, s_c2 = st.tabs(["Cobranzas", "Administrar Clientes"])
    with s_c1:
        if not df_clientes.empty:
            cl = st.selectbox("Cliente:", df_clientes["Nombre"].tolist(), key="cl_pago")
            mo = st.number_input("Monto:", min_value=0.0)
            me = st.selectbox("Forma:", ["Efectivo", "Transferencia", "Cheque", "eCheq"])
            det = ""
            if "Cheque" in me or "eCheq" in me:
                det = st.text_input("Detalle (N°, Banco, Vto):")
            if st.button("Confirmar Pago"):
                df_clientes.loc[df_clientes["Nombre"] == cl, "Saldo"] -= mo
                df_clientes.to_csv(ARCHIVOS["clientes"], index=False)
                n_m = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cl, "Tipo": "PAGO", "Monto": mo, "Metodo": me, "Detalle": det}])
                pd.concat([df_movs, n_m]).to_csv(ARCHIVOS["movs"], index=False)
                st.success("Pago registrado"); st.rerun()
    with s_c2:
        with st.expander("Añadir / Modificar Clientes"):
            edit_cli = st.data_editor(df_clientes, use_container_width=True, num_rows="dynamic")
            if st.button("Guardar Cambios Clientes"):
                edit_cli.to_csv(ARCHIVOS["clientes"], index=False)
                st.rerun()

# TAB PRESUPUESTADOR (Orden, Nota de Crédito, Impresión)
with tabs[3]:
    st.header("Presupuestador")
    cp = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["C. Final"], key="cp_pre")
    p1, p2, p3 = st.columns([2,1,1])
    with p1: it = st.selectbox("Producto:", df_stock["Accesorio"].tolist(), key="it_pre")
    with p2: ct = st.number_input("Cant:", min_value=1, key="ct_pre")
    with p3: ls = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
    
    if st.button("Agregar"):
        pr = df_stock[df_stock["Accesorio"] == it][ls].values[0]
        st.session_state.carrito.append({"Producto": it, "Cant": ct, "Precio U.": pr, "Subtotal": pr * ct})
        st.rerun()

    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        total = sum(i["Subtotal"] for i in st.session_state.carrito)
        st.write(f"### Total: $ {total:,.2f}")
        
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("✅ Generar Orden"):
                for i in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == i["Producto"], "Stock"] -= i["Cant"]
                if cp != "C. Final": df_clientes.loc[df_clientes["Nombre"] == cp, "Saldo"] += total
                df_stock.to_csv(ARCHIVOS["articulos"], index=False)
                df_clientes.to_csv(ARCHIVOS["clientes"], index=False)
                n_v = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cp, "Tipo": "VENTA", "Monto": total, "Metodo": ls, "Detalle": "Venta"}])
                pd.concat([df_movs, n_v]).to_csv(ARCHIVOS["movs"], index=False)
                st.session_state.carrito = []; st.success("Orden cargada"); st.rerun()
        with b2:
            if st.button("🔵 Nota de Crédito"):
                for i in st.session_state.carrito:
                    df_stock.loc[df_stock["Accesorio"] == i["Producto"], "Stock"] += i["Cant"]
                if cp != "C. Final": df_clientes.loc[df_clientes["Nombre"] == cp, "Saldo"] -= total
                df_stock.to_csv(ARCHIVOS["articulos"], index=False)
                df_clientes.to_csv(ARCHIVOS["clientes"], index=False)
                n_nc = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y"), "Cliente": cp, "Tipo": "N. CREDITO", "Monto": total, "Metodo": "-", "Detalle": "Devolución"}])
                pd.concat([df_movs, n_nc]).to_csv(ARCHIVOS["movs"], index=False)
                st.session_state.carrito = []; st.success("NC cargada"); st.rerun()
        with b3:
            pdf_data = generar_pdf_corregido(cp, st.session_state.carrito, total, "PRESUPUESTO")
            st.download_button("🖨️ Imprimir PDF", pdf_data, f"Presu_{cp}.pdf")
        with b4:
            if st.button("🗑️ Vaciar"): st.session_state.carrito = []; st.rerun()

# CIERRE Y REMITOS (Completados)
with tabs[5]:
    st.header("Cierre de Caja")
    st.metric("Deuda Total Clientes", f"$ {df_clientes['Saldo'].sum():,.2f}")
    st.subheader("Cheques en cartera")
    st.dataframe(df_movs[df_movs["Metodo"].str.contains("Cheque|eCheq", na=False)], use_container_width=True)

with tabs[6]:
    st.header("Generador de Remitos")
    cr = st.selectbox("Enviar a:", df_clientes["Nombre"].tolist(), key="cr_rem")
    r1, r2 = st.columns([3,1])
    with r1: pr_r = st.selectbox("Producto:", df_stock["Accesorio"].tolist(), key="pr_rem")
    with r2: ct_r = st.number_input("Cant:", min_value=1, key="ct_rem")
    if st.button("Sumar al Remito"):
        st.session_state.remito_items.append({"Producto": pr_r, "Cant": ct_r, "Precio U.": 0, "Subtotal": 0})
        st.rerun()
    if st.session_state.remito_items:
        st.table(st.session_state.remito_items)
        pdf_rem = generar_pdf_corregido(cr, st.session_state.remito_items, 0, "REMITO DE ENTREGA")
        st.download_button("Bajar Remito PDF", pdf_rem, f"Remito_{cr}.pdf")
        if st.button("Borrar Remito"): st.session_state.remito_items = []; st.rerun()

# RESTO DE TABS (Vistas)
with tabs[0]: st.dataframe(df_stock, use_container_width=True)
with tabs[4]: st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)
with tabs[7]:
    st.header("Maestro")
    ed_st = st.data_editor(df_stock, use_container_width=True)
    if st.button("Guardar Todo"):
        ed_st.to_csv(ARCHIVOS["articulos"], index=False)
        st.success("Guardado"); st.rerun()
