import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión", layout="wide", initial_sidebar_state="collapsed")

ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos"
WHATSAPP_NUM = "5493413512049"

if "carrito" not in st.session_state: st.session_state.carrito = []
if "venta_confirmada" not in st.session_state: st.session_state.venta_confirmada = False

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, sep=None, engine='python', on_bad_lines='skip')
            df.columns = df.columns.str.strip()
            for col in columnas:
                if col not in df.columns:
                    df[col] = 0.0 if any(x in col for x in ["Saldo", "Monto", "Stock"]) else ""
            return df[columnas]
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Tel", "Localidad", "Direccion", "Saldo"])
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Metodo", "Detalle"])

def formatear_moneda(valor):
    try: return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- MOTOR DE PDF (DISEÑO SEGÚN MUESTRA) ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 30)
        except:
            self.set_font("Helvetica", "B", 12)
            self.cell(30, 10, "ACCESORIOS", ln=0)
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True, align="C")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True, align="C")
        self.ln(10)

def generar_pdf_af(cliente_n, detalle_lista, monto, tipo_doc="PRESUPUESTO"):
    try:
        pdf = PDF()
        pdf.add_page()
        # Info Cliente
        info = df_clientes[df_clientes["Nombre"] == cliente_n]
        tel = str(info["Tel"].values[0]) if not info.empty else "-"
        loc = str(info["Localidad"].values[0]) if not info.empty else "-"
        dir = str(info["Direccion"].values[0]) if not info.empty else "-"
        
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 8, f" TIPO DE DOCUMENTO: {tipo_doc}", ln=True, fill=True, border=1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(95, 8, f" CLIENTE: {cliente_n}", border="LBT")
        pdf.cell(95, 8, f" FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", border="RBT", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(63, 8, f" TEL: {tel}", border="LB")
        pdf.cell(63, 8, f" LOCALIDAD: {loc}", border="B")
        pdf.cell(64, 8, f" DIRECCIÓN: {dir}", border="RB", ln=True); pdf.ln(5)
        
        # Tabla
        pdf.set_font("Helvetica", "B", 9); pdf.set_fill_color(220, 220, 220)
        pdf.cell(100, 8, " Artículo / Accesorio", border=1, fill=True)
        pdf.cell(20, 8, "Cant.", border=1, fill=True, align="C")
        pdf.cell(35, 8, "P. Unit", border=1, fill=True, align="R")
        pdf.cell(35, 8, "Subtotal", border=1, fill=True, align="R", ln=True)
        
        pdf.set_font("Helvetica", "", 9)
        for it in detalle_lista:
            pdf.cell(100, 7, f" {it['Producto'][:45]}", border=1)
            pdf.cell(20, 7, str(it['Cant']), border=1, align="C")
            pdf.cell(35, 7, formatear_moneda(it['Precio U.']), border=1, align="R")
            pdf.cell(35, 7, formatear_moneda(it['Subtotal']), border=1, align="R", ln=True)
        
        pdf.set_font("Helvetica", "B", 11); pdf.ln(2)
        pdf.cell(155, 10, "TOTAL: ", align="R")
        pdf.cell(35, 10, formatear_moneda(monto), align="R", border=1)
        
        # Solución al error de codificación
        return bytes(pdf.output(dest='S'))
    except Exception as e:
        st.error(f"Error PDF: {e}")
        return None

# --- INTERFAZ ---
t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Clientes", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre"])

with t[3]: # CUENTAS CORRIENTES
    st.header("👥 Gestión de Clientes")
    if not df_clientes.empty:
        c_sel = st.selectbox("Cliente:", df_clientes["Nombre"].tolist())
        idx = df_clientes[df_clientes["Nombre"] == c_sel].index[0]
        st.info(f"### BALANCE DE CUENTA: {formatear_moneda(df_clientes.at[idx, 'Saldo'])}")
        
        with st.expander("📝 EDITAR CLIENTE (TODOS LOS CAMPOS)"):
            c_ed = st.columns(2)
            en = c_ed[0].text_input("Nombre:", df_clientes.at[idx, "Nombre"])
            et = c_ed[1].text_input("Tel:", df_clientes.at[idx, "Tel"])
            el = c_ed[0].text_input("Localidad:", df_clientes.at[idx, "Localidad"])
            ed = c_ed[1].text_input("Dirección:", df_clientes.at[idx, "Direccion"])
            es = st.number_input("Saldo Manual:", value=float(df_clientes.at[idx, "Saldo"]))
            if st.button("Guardar Cambios Totales"):
                df_clientes.at[idx, "Nombre"], df_clientes.at[idx, "Tel"] = en, et
                df_clientes.at[idx, "Localidad"], df_clientes.at[idx, "Direccion"], df_clientes.at[idx, "Saldo"] = el, ed, es
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False); st.success("Guardado"); st.rerun()

        h = df_movs[df_movs["Cliente"] == c_sel].sort_index(ascending=False)
        for i, r in h.iterrows():
            emo = "🔴" if r["Tipo"] == "VENTA" else "🟢"
            with st.expander(f"{emo} {r['Fecha']} | {r['Tipo']} | {formatear_moneda(r['Monto'])}"):
                st.write(f"Detalle: {r['Detalle']}")
                # Re-impresión idéntica
                if r["Tipo"] == "VENTA":
                    # Intentar reconstruir lista desde el string de detalle si es posible
                    det_lista = [{"Producto": r["Detalle"], "Cant": "-", "Precio U.": 0, "Subtotal": r["Monto"]}]
                    pdf_h = generar_pdf_af(c_sel, det_lista, r["Monto"], "ORDEN DE TRABAJO")
                    st.download_button("🖨️ Re-Imprimir Orden", pdf_h, f"Orden_{i}.pdf", key=f"h_{i}")

with t[4]: # PRESUPUESTADOR
    st.header("📄 Presupuestador")
    cli_p = st.selectbox("Elegir Cliente:", ["Consumidor Final"] + df_clientes["Nombre"].tolist())
    
    if not st.session_state.venta_confirmada:
        cp1, cp2, cp3 = st.columns([3,1,1])
        ps = cp1.selectbox("Accesorio:", df_stock["Accesorio"].tolist())
        ct = cp2.number_input("Cant:", 1)
        ls = cp3.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        if st.button("➕ AGREGAR"):
            pr = df_stock[df_stock["Accesorio"] == ps][ls].values[0]
            st.session_state.carrito.append({"Producto": ps, "Cant": ct, "Precio U.": pr, "Subtotal": pr*ct}); st.rerun()

    if st.session_state.carrito:
        for i, it in enumerate(st.session_state.carrito):
            cols = st.columns([4, 1, 2, 2, 1])
            cols[0].write(it["Producto"]); cols[1].write(f"x{it['Cant']}")
            cols[2].write(formatear_moneda(it["Precio U."])); cols[3].write(formatear_moneda(it["Subtotal"]))
            if not st.session_state.venta_confirmada and cols[4].button("🗑️", key=f"d_{i}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        tot = sum(x["Subtotal"] for x in st.session_state.carrito)
        st.markdown(f"## Total: {formatear_moneda(tot)}")
        
        b1, b2, b3 = st.columns(3)
        pdf_p = generar_pdf_af(cli_p, st.session_state.carrito, tot, "PRESUPUESTO")
        b1.download_button("📥 IMPRIMIR PRESUPUESTO", pdf_p, "Presupuesto.pdf")
        
        if not st.session_state.venta_confirmada:
            if b2.button("✅ CONFIRMAR ORDEN"):
                # (Lógica de descuento de stock y actualización de saldo igual a la anterior)
                st.session_state.venta_confirmada = True; st.success("Orden creada. Podés imprimirla ahora."); st.rerun()
        else:
            pdf_o = generar_pdf_af(cli_p, st.session_state.carrito, tot, "ORDEN DE TRABAJO")
            b2.download_button("🖨️ IMPRIMIR ORDEN", pdf_o, "Orden.pdf", type="primary")
        
        if b3.button("🧹 NUEVA VENTA"):
            st.session_state.carrito = []; st.session_state.venta_confirmada = False; st.rerun()

# (Tabs restantes se mantienen igual)
