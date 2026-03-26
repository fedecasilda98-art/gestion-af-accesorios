import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión Pro", layout="wide", initial_sidebar_state="collapsed")

ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos"

if "carrito" not in st.session_state: st.session_state.carrito = []
if "venta_confirmada" not in st.session_state: st.session_state.venta_confirmada = False

# --- MOTOR DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, sep=None, engine='python', on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns:
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Stock", "Lista", "Costo", "Flete"]) else ""
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"])
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"])

def formatear_moneda(valor):
    try: return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- MOTOR DE PDF (DISEÑO SEGÚN TU PDF) ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 30)
        except: pass
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True, align="C")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True, align="C")
        self.ln(10)

def generar_pdf_af(cliente_n, carrito, total, tipo_doc="PRESUPUESTO"):
    try:
        pdf = PDF(); pdf.add_page()
        c_info = df_clientes[df_clientes["Nombre"] == cliente_n]
        tel = str(c_info["Tel"].values[0]) if not c_info.empty else "-"
        loc = str(c_info["Localidad"].values[0]) if not c_info.empty else "-"
        dir = str(c_info["Direccion"].values[0]) if not c_info.empty else "-"
        
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {tipo_doc}", ln=True, fill=True, border=1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(95, 8, f" CLIENTE: {cliente_n}", border="LBT")
        pdf.cell(95, 8, f" FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", border="RBT", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(63, 8, f" TEL: {tel}", border="LB")
        pdf.cell(63, 8, f" LOCALIDAD: {loc}", border="B")
        pdf.cell(64, 8, f" DIRECCIÓN: {dir}", border="RB", ln=True); pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 9); pdf.set_fill_color(220, 220, 220)
        pdf.cell(100, 8, " Artículo / Accesorio", border=1, fill=True)
        pdf.cell(20, 8, "Cant.", border=1, fill=True, align="C")
        pdf.cell(35, 8, "P. Unit", border=1, fill=True, align="R")
        pdf.cell(35, 8, "Subtotal", border=1, fill=True, align="R", ln=True)
        
        pdf.set_font("Helvetica", "", 9)
        for item in carrito:
            pdf.cell(100, 7, f" {item['Producto']}", border=1)
            pdf.cell(20, 7, str(item['Cant']), border=1, align="C")
            pdf.cell(35, 7, formatear_moneda(item['Precio U.']), border=1, align="R")
            pdf.cell(35, 7, formatear_moneda(item['Subtotal']), border=1, align="R", ln=True)
        
        pdf.set_font("Helvetica", "B", 11); pdf.ln(2)
        pdf.cell(155, 10, "TOTAL: ", align="R")
        pdf.cell(35, 10, formatear_moneda(total), align="R", border=1)
        return bytes(pdf.output(dest='S'))
    except: return None

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Clientes", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre"])

with tabs[0]: # STOCK
    st.header("📊 Stock Actual")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE
    st.header("🚚 Carga por Lote")
    df_l = st.data_editor(pd.DataFrame(columns=df_stock.columns), num_rows="dynamic")
    if st.button("Integrar a Stock"):
        pd.concat([df_stock, df_l.dropna(subset=["Accesorio"])]).to_csv(ARCHIVO_ARTICULOS, index=False); st.rerun()

with tabs[2]: # MAESTRO
    st.header("⚙️ Editor Maestro")
    df_m = st.data_editor(df_stock, use_container_width=True, hide_index=True)
    if st.button("Guardar Cambios Maestro"): df_m.to_csv(ARCHIVO_ARTICULOS, index=False); st.rerun()

with tabs[3]: # CLIENTES (COLORES Y DESCARGA)
    st.header("👥 Gestión de Clientes")
    with st.expander("➕ NUEVO CLIENTE"):
        with st.form("n_c"):
            cn, ct, cl, cd, cs = st.text_input("Nombre"), st.text_input("Tel"), st.text_input("Localidad"), st.text_input("Dirección"), st.number_input("Saldo Inicial", 0.0)
            if st.form_submit_button("Crear"):
                pd.concat([df_clientes, pd.DataFrame([{"Nombre":cn,"Tel":ct,"Localidad":cl,"Direccion":cd,"Saldo":cs}])]).to_csv(ARCHIVO_CLIENTES, index=False); st.rerun()

    if not df_clientes.empty:
        c_sel = st.selectbox("Elegir Cliente:", df_clientes["Nombre"].tolist())
        idx = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
        st.info(f"### BALANCE DE CUENTA: {formatear_moneda(df_clientes.at[idx, 'Saldo'])}")
        
        with st.expander("📝 MODIFICAR TODO (Nombre, Tel, Saldo, etc)"):
            en, et = st.text_input("Nombre", df_clientes.at[idx, "Nombre"]), st.text_input("Tel", df_clientes.at[idx, "Tel"])
            el, ed = st.text_input("Localidad", df_clientes.at[idx, "Localidad"]), st.text_input("Dirección", df_clientes.at[idx, "Direccion"])
            es = st.number_input("Saldo Manual", value=float(df_clientes.at[idx, "Saldo"]))
            if st.button("Actualizar Cliente"):
                df_clientes.at[idx, "Nombre"], df_clientes.at[idx, "Tel"], df_clientes.at[idx, "Localidad"], df_clientes.at[idx, "Direccion"], df_clientes.at[idx, "Saldo"] = en, et, el, ed, es
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Datos actualizados"); st.rerun()

        st.subheader("Historial de Movimientos")
        h = df_movs[df_movs["Cliente"] == c_sel].sort_index(ascending=False)
        for i, r in h.iterrows():
            color = "🔴" if r["Tipo"] == "VENTA" else "🟢"
            with st.expander(f"{color} {r['Fecha']} | {r['Tipo']} | {formatear_moneda(r['Monto'])}"):
                st.write(f"Detalle: {r['Detalle']}")
                if r["Tipo"] == "VENTA":
                    # Re-impresión desde historial
                    pdf_h = generar_pdf_af(c_sel, [{"Producto": r["Detalle"], "Cant": "1", "Precio U.": r["Monto"], "Subtotal": r["Monto"]}], r["Monto"], "ORDEN DE TRABAJO")
                    st.download_button("🖨️ Re-Imprimir Orden", pdf_h, f"Orden_{i}.pdf", key=f"re_{i}")

with tabs[4]: # PRESUPUESTADOR COMPLETO
    st.header("📄 Presupuestador")
    cli_p = st.selectbox("Seleccionar Cliente:", ["Consumidor Final"] + df_clientes["Nombre"].tolist(), key="cp")
    if not st.session_state.venta_confirmada:
        col1, col2, col3 = st.columns([3,1,1])
        prod = col1.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        cant = col2.number_input("Cant:", 1)
        list_t = col3.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        if st.button("➕ AGREGAR AL CARRITO"):
            pre = df_stock[df_stock["Accesorio"] == prod][list_t].values[0]
            st.session_state.carrito.append({"Producto": prod, "Cant": cant, "Precio U.": pre, "Subtotal": pre*cant}); st.rerun()

    if st.session_state.carrito:
        for i, it in enumerate(st.session_state.carrito):
            cx = st.columns([4, 1, 2, 2, 1])
            cx[0].write(it["Producto"]); cx[1].write(f"x{it['Cant']}")
            cx[2].write(formatear_moneda(it["Precio U."])); cx[3].write(formatear_moneda(it["Subtotal"]))
            if not st.session_state.venta_confirmada and cx[4].button("🗑️", key=f"d_{i}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        tot = sum(x["Subtotal"] for x in st.session_state.carrito)
        st.markdown(f"## TOTAL: {formatear_moneda(tot)}")
        
        b1, b2, b3 = st.columns(3)
        pdf_p = generar_pdf_af(cli_p, st.session_state.carrito, tot, "PRESUPUESTO")
        b1.download_button("📥 IMPRIMIR PRESUPUESTO", pdf_p, "Presupuesto.pdf")
        
        if not st.session_state.venta_confirmada:
            if b2.button("✅ CONFIRMAR Y CREAR ORDEN"):
                det = ", ".join([f"{x['Cant']}x {x['Producto']}" for x in st.session_state.carrito])
                for x in st.session_state.carrito: df_stock.loc[df_stock["Accesorio"] == x["Producto"], "Stock"] -= x["Cant"]
                if cli_p != "Consumidor Final": df_clientes.loc[df_clientes["Nombre"] == cli_p, "Saldo"] += tot
                pd.concat([df_movs, pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": tot, "Metodo": "-", "Detalle": det}])]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                df_stock.to_csv(ARCHIVO_ARTICULOS, index=False); df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                st.session_state.venta_confirmada = True; st.rerun()
        else:
            pdf_o = generar_pdf_af(cli_p, st.session_state.carrito, tot, "ORDEN DE TRABAJO")
            b2.download_button("🖨️ IMPRIMIR ORDEN", pdf_o, "Orden.pdf", type="primary")
        
        if b3.button("🧹 NUEVA VENTA / LIMPIAR"):
            st.session_state.carrito = []; st.session_state.venta_confirmada = False; st.rerun()

with tabs[5]: st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True)
with tabs[6]: st.metric("Saldo Global en Calle", formatear_moneda(df_clientes["Saldo"].sum()))
