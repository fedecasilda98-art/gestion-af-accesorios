import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import re

# --- CONFIGURACIÓN DE RUTAS ---
st.set_page_config(page_title="AF Accesorios - Gestión y Catálogo", layout="wide")
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
ARCHIVO_ORDENES_LOG = "log_ordenes.csv"
CARPETA_PRESUPUESTOS = "presupuestos_pdf"
CARPETA_ORDENES = "ordenes_trabajo"
CARPETA_FOTOS = "fotos_productos" 
LOGO_PATH = "logo.jpg" 

for carpeta in [CARPETA_PRESUPUESTOS, CARPETA_ORDENES, CARPETA_FOTOS]:
    if not os.path.exists(carpeta): os.makedirs(carpeta)

# --- ESTADO DE SESIÓN ---
if "carrito" not in st.session_state: 
    st.session_state.carrito = pd.DataFrame(columns=["Artículo", "Cantidad", "Precio Unitario", "Subtotal"])
if "form_id" not in st.session_state: 
    st.session_state.form_id = 0

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            if "Descripcion" not in df.columns and archivo == ARCHIVO_ARTICULOS:
                df["Descripcion"] = ""
            cols_num = ["Stock", "Saldo", "Monto", "Cantidad", "Subtotal", "Precio Unitario", "Costo Base", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

def registrar_movimiento(cliente, tipo, monto, detalle, nro_orden=None):
    df_mov = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Detalle", "Nro_Orden"])
    nuevo = pd.DataFrame([[datetime.now().strftime("%d/%m/%Y %H:%M"), cliente, tipo, monto, detalle, nro_orden]], columns=df_mov.columns)
    guardar_datos(pd.concat([df_mov, nuevo], ignore_index=True), ARCHIVO_MOVIMIENTOS)

# --- GENERADORES DE PDF ---
def generar_pdf_documento(cliente_nom, df_carrito, total, tipo="PRESUPUESTO", nro_orden=None):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists(LOGO_PATH):
        try: pdf.image(LOGO_PATH, 10, 8, 33); pdf.ln(20)
        except: pdf.set_font("Arial", "B", 16); pdf.cell(100, 10, txt="AF ACCESORIOS"); pdf.ln(10)
    else:
        pdf.set_font("Arial", "B", 16); pdf.cell(100, 10, txt="AF ACCESORIOS"); pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    titulo = f"{tipo} # {nro_orden}" if nro_orden else tipo
    pdf.cell(0, 10, txt=titulo, ln=True, align="R")
    pdf.set_font("Arial", "B", 10); pdf.cell(0, 8, txt=f"Cliente: {cliente_nom}", ln=True)
    pdf.set_font("Arial", "", 9); pdf.cell(100, 8, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", "B", 9)
    pdf.cell(90, 10, "Articulo", 1, 0, 'L', True); pdf.cell(20, 10, "Cant.", 1, 0, 'C', True)
    pdf.cell(35, 10, "P. Unit", 1, 0, 'C', True); pdf.cell(45, 10, "Subtotal", 1, 1, 'C', True)
    
    pdf.set_font("Arial", "", 9)
    for _, row in df_carrito.iterrows():
        pdf.cell(90, 10, str(row["Artículo"])[:45], 1)
        pdf.cell(20, 10, str(int(row["Cantidad"])), 1, 0, 'C')
        pdf.cell(35, 10, f"$ {row['Precio Unitario']:,.2f}", 1, 0, 'R')
        pdf.cell(45, 10, f"$ {row['Subtotal']:,.2f}", 1, 1, 'R')
    
    pdf.ln(5); pdf.set_font("Arial", "B", 12)
    pdf.cell(145, 10, "TOTAL:", align="R"); pdf.cell(45, 10, f"$ {total:,.2f}", 1, 1, 'R')
    
    folder = CARPETA_PRESUPUESTOS if tipo=="PRESUPUESTO" else CARPETA_ORDENES
    nom_arch = f"{tipo}_{nro_orden if nro_orden else 'P'}_{cliente_nom}.pdf"
    ruta = os.path.join(folder, nom_arch)
    pdf.output(ruta)
    return ruta

def generar_pdf_catalogo(df):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    if os.path.exists(LOGO_PATH): pdf.image(LOGO_PATH, 10, 8, 30)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "CATALOGO DE PRODUCTOS - AF ACCESORIOS", ln=True, align="C")
    pdf.ln(20)

    items = df.to_dict("records")
    for i, item in enumerate(items):
        col = i % 2
        if col == 0 and i > 0: pdf.ln(5)
        x = 10 + (col * 100)
        y = pdf.get_y()
        if y > 230:
            pdf.add_page(); y = 40

        pdf.rect(x, y, 95, 55)
        
        # BUSQUEDA FLEXIBLE DE FOTO
        nombre_base = re.sub(r'[^a-zA-Z0-9\s]', '', str(item['Accesorio']))
        encontrada = False
        for ext in [".jpg", ".JPG", ".png", ".PNG", ".jpeg"]:
            foto_path = os.path.join(CARPETA_FOTOS, f"{nombre_base}{ext}")
            if os.path.exists(foto_path):
                pdf.image(foto_path, x + 2, y + 2, 35, 35)
                encontrada = True
                break
        
        if not encontrada:
            pdf.set_font("Arial", "I", 7); pdf.set_xy(x + 2, y + 20)
            pdf.cell(35, 10, "Sin Foto", 0, 0, 'C')
            st.warning(f"Falta foto para: {item['Accesorio']} (Buscado como: {nombre_base})")
        
        pdf.set_font("Arial", "B", 10); pdf.set_xy(x + 40, y + 5)
        pdf.multi_cell(50, 5, str(item['Accesorio']))
        
        pdf.set_font("Arial", "", 8); pdf.set_xy(x + 40, y + 15)
        pdf.multi_cell(50, 4, str(item.get('Descripcion', ''))[:80])
        
        pdf.set_font("Arial", "B", 11); pdf.set_text_color(200, 0, 0)
        pdf.set_xy(x + 40, y + 45)
        pdf.cell(50, 5, f"Precio: $ {item['Lista 1 (Cheques)']:,.2f}")
        pdf.set_text_color(0, 0, 0)
        if col == 1: pdf.set_y(y + 60)

    ruta = "Catalogo_AF_Accesorios.pdf"
    pdf.output(ruta)
    return ruta

# --- CARGA INICIAL ---
df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Teléfono", "Localidad", "Saldo"])

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "📥 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestos", "📋 Órdenes", "📖 Catálogo", "🏁 Cierre"])

with tabs[0]: st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE
    st.header("📥 Ingreso por Lote")
    df_lote = st.data_editor(pd.DataFrame(columns=["Artículo", "Cantidad"]), num_rows="dynamic", use_container_width=True)
    if st.button("Procesar Lote"):
        for _, f in df_lote.iterrows():
            if pd.notna(f["Artículo"]) and f["Artículo"] in df_stock["Accesorio"].values:
                idx = df_stock[df_stock["Accesorio"] == f["Artículo"]].index[0]
                try: df_stock.at[idx, "Stock"] += float(str(f["Cantidad"]).replace(',', '.'))
                except: pass
        guardar_datos(df_stock, ARCHIVO_ARTICULOS); st.success("Stock actualizado."); st.rerun()

with tabs[2]: # MAESTRO
    st.header("⚙️ Maestro de Artículos")
    with st.expander("➕ Agregar Nuevo Artículo"):
        with st.form("alta_m"):
            c1, c2, c3 = st.columns(3)
            rb = c1.text_input("Rubro"); pr = c2.text_input("Proveedor"); nm = c3.text_input("Nombre Accesorio")
            stk = c1.number_input("Stock", 0); cst = c2.number_input("Costo", 0.0); gan = c3.number_input("% Ganancia", 35.0)
            if st.form_submit_button("Guardar"):
                l1 = cst * (1 + (gan/100)); l2 = l1 * 0.9
                nuevo = pd.DataFrame([[rb.upper(), pr, nm.upper(), stk, cst, 0, gan, l1, l2, ""]], columns=df_stock.columns)
                df_stock = pd.concat([df_stock, nuevo], ignore_index=True)
                guardar_datos(df_stock, ARCHIVO_ARTICULOS); st.rerun()
    st.subheader("🔍 Filtros y Edición")
    f1, f2 = st.columns(2)
    fr = f1.multiselect("Rubro:", sorted(df_stock["Rubro"].unique().tolist()))
    fp = f2.multiselect("Proveedor:", sorted(df_stock["Proveedor"].unique().tolist()))
    df_f = df_stock.copy()
    if fr: df_f = df_f[df_f["Rubro"].isin(fr)]
    if fp: df_f = df_f[df_f["Proveedor"].isin(fp)]
    df_m = st.data_editor(df_f, use_container_width=True, hide_index=True)
    if st.button("Guardar Cambios Maestro"):
        df_stock.update(df_m); guardar_datos(df_stock, ARCHIVO_ARTICULOS); st.success("Guardado"); st.rerun()

with tabs[3]: # CTA CTE
    st.header("👥 Gestión de Clientes")
    with st.expander("🛠️ Admin"):
        sub_t = st.tabs(["✨ Nuevo", "✏️ Modificar", "🗑️ Eliminar"])
        with sub_t[0]:
            with st.form("fc"):
                nn=st.text_input("Nombre"); tn=st.text_input("Tel"); ln=st.text_input("Loc"); sn=st.number_input("Saldo", 0.0)
                if st.form_submit_button("Crear"):
                    df_clientes = pd.concat([df_clientes, pd.DataFrame([[nn,tn,ln,sn]], columns=df_clientes.columns)], ignore_index=True)
                    guardar_datos(df_clientes, ARCHIVO_CLIENTES); st.rerun()
        with sub_t[1]:
            cm = st.selectbox("Editar:", df_clientes["Nombre"].tolist())
            if cm:
                d = df_clientes[df_clientes["Nombre"]==cm].iloc[0]
                with st.form("fm"):
                    tm=st.text_input("Tel", value=str(d["Teléfono"])); lm=st.text_input("Loc", value=str(d["Localidad"])); sm=st.number_input("Saldo", value=float(d["Saldo"]))
                    if st.form_submit_button("Actualizar"):
                        df_clientes.loc[df_clientes["Nombre"]==cm, ["Teléfono","Localidad","Saldo"]] = [tm,lm,sm]
                        guardar_datos(df_clientes, ARCHIVO_CLIENTES); st.rerun()
    sel_c = st.selectbox("Cuenta:", ["Mostrador"] + sorted(df_clientes["Nombre"].tolist()))
    if sel_c != "Mostrador":
        idx = df_clientes[df_clientes["Nombre"]==sel_c].index[0]
        st.metric("Saldo", f"$ {df_clientes.at[idx, 'Saldo']:,.2f}")
        p = st.number_input("Registrar Cobro", 0.0)
        if st.button("Confirmar Pago"):
            df_clientes.at[idx, "Saldo"] += p
            registrar_movimiento(sel_c, "PAGO", p, "Cobro adm")
            guardar_datos(df_clientes, ARCHIVO_CLIENTES); st.rerun()

with tabs[4]: # PRESUPUESTADOR
    st.header("📄 Presupuestos / OT")
    c1, c2 = st.columns(2)
    cp = c1.selectbox("Cliente:", ["Mostrador"] + sorted(df_clientes["Nombre"].tolist()), key="sel_cli")
    lp = c2.selectbox("Lista de Precio:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="sel_lis")
    with st.form(key=f"f_{st.session_state.form_id}", clear_on_submit=True):
        ci1, ci2 = st.columns([3, 1])
        it = ci1.selectbox("Accesorio:", sorted(df_stock["Accesorio"].tolist()))
        ca = ci2.text_input("Cant", "1")
        if st.form_submit_button("➕"):
            r = df_stock[df_stock["Accesorio"] == it].iloc[0]
            pu = r["Lista 1 (Cheques)"] if "1" in lp else r["Lista 2 (Efectivo)"]
            cv = float(ca.replace(',','.'))
            st.session_state.carrito = pd.concat([st.session_state.carrito, pd.DataFrame([[it, cv, pu, cv*pu]], columns=st.session_state.carrito.columns)], ignore_index=True)
            st.session_state.form_id += 1; st.rerun()
    if not st.session_state.carrito.empty:
        st.session_state.carrito = st.data_editor(st.session_state.carrito, num_rows="dynamic")
        tot = st.session_state.carrito["Subtotal"].sum()
        st.subheader(f"Total: $ {tot:,.2f}")
        b1, b2 = st.columns(2)
        if b1.button("📄 Presupuesto (PDF)"):
            path = generar_pdf_documento(cp, st.session_state.carrito, tot, "PRESUPUESTO")
            with open(path, "rb") as f: st.download_button("📥 DESCARGAR PRESUPUESTO", f, file_name=os.path.basename(path))
        if b2.button("📋 Confirmar Orden"):
            df_m_log = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Nro_Orden"])
            nro = 1 if df_m_log.empty or df_m_log["Nro_Orden"].isna().all() else int(df_m_log["Nro_Orden"].max() + 1)
            path = generar_pdf_documento(cp, st.session_state.carrito, tot, "ORDEN", nro)
            if cp != "Mostrador":
                df_clientes.loc[df_clientes["Nombre"]==cp, "Saldo"] -= tot
                df_log = cargar_datos(ARCHIVO_ORDENES_LOG, ["Nro_Orden", "Cliente", "Articulo", "Cantidad", "Subtotal"])
                tmp = st.session_state.carrito.copy().rename(columns={"Artículo":"Articulo"})
                tmp["Nro_Orden"] = nro; tmp["Cliente"] = cp
                guardar_datos(pd.concat([df_log, tmp], ignore_index=True), ARCHIVO_ORDENES_LOG)
            registrar_movimiento(cp, "VENTA", -tot, f"OT #{nro}", nro)
            for _, r in st.session_state.carrito.iterrows(): df_stock.loc[df_stock["Accesorio"]==r["Artículo"], "Stock"] -= r["Cantidad"]
            guardar_datos(df_stock, ARCHIVO_ARTICULOS); guardar_datos(df_clientes, ARCHIVO_CLIENTES)
            st.success(f"OT #{nro} generada.")
            with open(path, "rb") as f: st.download_button("📥 DESCARGAR OT", f, file_name=os.path.basename(path))
            st.session_state.carrito = pd.DataFrame(columns=st.session_state.carrito.columns)

with tabs[5]: # HISTORIAL
    st.header("📋 Historial de Archivos")
    for fld, lbl in [(CARPETA_ORDENES, "ORDENES"), (CARPETA_PRESUPUESTOS, "PRESUPUESTOS")]:
        st.subheader(lbl)
        for f in os.listdir(fld):
            c1, c2 = st.columns([0.8, 0.2])
            c1.write(f"📄 {f}")
            with open(os.path.join(fld, f), "rb") as b: c2.download_button("Bajar", b, file_name=f, key=f"dl_{f}")

with tabs[6]: # CATÁLOGO
    st.header("📖 Generador de Catálogo")
    st.info("Escribí descripciones y generá el PDF. Si falta alguna foto, te avisaré aquí abajo.")
    df_cat = st.data_editor(df_stock[["Accesorio", "Rubro", "Descripcion", "Lista 1 (Cheques)"]], use_container_width=True, hide_index=True)
    if st.button("🚀 GENERAR CATÁLOGO PDF"):
        df_stock["Descripcion"] = df_cat["Descripcion"]
        guardar_datos(df_stock, ARCHIVO_ARTICULOS)
        ruta_cat = generar_pdf_catalogo(df_cat)
        with open(ruta_cat, "rb") as f: st.download_button("📥 DESCARGAR CATÁLOGO", f, file_name="Catalogo_AF.pdf")

with tabs[7]: # CIERRE
    st.header("🏁 Cierre del Día")
    h = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha","Tipo","Monto"]).dropna()
    st.metric("Cobros hoy", f"$ {h[h['Tipo']=='PAGO']['Monto'].sum():,.2f}")