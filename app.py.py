import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# --- BLOQUE DE DIAGNÓSTICO ---
st.sidebar.write("### 🔍 Estado de Archivos")
if os.path.exists("data"):
    st.sidebar.success("Carpeta 'data' encontrada")
    archivos_en_data = os.listdir("data")
    st.sidebar.write(f"Archivos: {archivos_en_data}")
else:
    st.sidebar.error("Carpeta 'data' NO EXISTE")

ARCHIVO_ARTICULOS = "data/lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "data/clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "data/movimientos_clientes.csv"
ARCHIVO_REGISTRO_LOTES = "data/registro_lotes.csv"
CARPETA_FOTOS = "data/fotos_productos"
WHATSAPP_NUM = "5493413512049"

# Detectar Modo Cliente
es_cliente = st.query_params.get("modo") == "cliente"

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
COLS_REGISTRO_LOTES = ["Fecha", "Articulos", "Costo Total Compra"]

df_stock = cargar_datos(ARCHIVO_ARTICULOS, COLS_ARTICULOS)
df_clientes = cargar_datos(ARCHIVO_CLIENTES, COLS_CLIENTES)
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, COLS_MOVS)
df_lotes_historial = cargar_datos(ARCHIVO_REGISTRO_LOTES, COLS_REGISTRO_LOTES)

# Inicializar estados de sesión
if "carrito" not in st.session_state: st.session_state.carrito = []
if "remito_items" not in st.session_state: st.session_state.remito_items = []
if "orden_lista" not in st.session_state: st.session_state.orden_lista = None
if "confirmar_orden" not in st.session_state: st.session_state.confirmar_orden = False
if "confirmar_nc" not in st.session_state: st.session_state.confirmar_nc = False

# --- UTILIDADES DE FORMATO ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- CLASE PDF ---
class PDF(FPDF):
    def header(self):
        try: self.image('logo.jpg', 10, 8, 33)
        except: pass
        self.set_font("Helvetica", "B", 16)
        self.cell(40)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True)
        self.set_font("Helvetica", "", 10)
        self.cell(40)
        self.cell(0, 5, "Casilda, Santa Fe | WhatsApp: +54 9 341 351-2049", ln=True)
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
        pdf.cell(190, 7, f" DIRECCIÓN: {dir}", border="LRB", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(200, 200, 200)
        pdf.cell(100, 10, " Artículo / Accesorio", border=1, fill=True)
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
        if isinstance(res, (bytearray, bytes)):
            return bytes(res)
        else:
            return res.encode('latin-1', 'replace')
    except Exception as e:
        st.error(f"Error PDF: {str(e)}")
        return b""

# --- INTERFAZ ---
if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busqueda = st.text_input("Buscar producto...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    cols = st.columns(3)
    for idx, row in df_ver.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{nombre_foto}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                st.subheader(row["Accesorio"])
                l_tipo = st.radio("Condición:", ["Cheques", "Efectivo/Transf."], key=f"cr_{idx}")
                p = row["Lista 1 (Cheques)"] if l_tipo == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**{formatear_moneda(p)}**")
                c = st.number_input("Cantidad", 0, key=f"cn_{idx}")
                if st.button("Pedir", key=f"cb_{idx}"):
                    msg = f"Hola! Pedido de {c}x {row['Accesorio']} ({l_tipo})."
                    st.markdown(f"[Confirmar en WhatsApp](https://wa.me/{WHATSAPP_NUM}?text={msg})")
else:
    tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja", "📦 Remitos"])

    with tabs[0]: # STOCK
        st.header("Inventario Actual")
        if not df_stock.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Costo Stock", formatear_moneda((df_stock['Costo Base'] * df_stock['Stock']).sum()))
            c2.metric("Total Lista 1", formatear_moneda((df_stock['Lista 1 (Cheques)'] * df_stock['Stock']).sum()))
            c3.metric("Total Lista 2", formatear_moneda((df_stock['Lista 2 (Efectivo)'] * df_stock['Stock']).sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # LOTE
        st.header("🚚 Ingreso de Mercadería")
        tab_carga, tab_hist_ingresos = st.tabs(["📥 Cargar Lote", "📜 Historial de Ingresos"])

        with tab_carga:
            if "lote_temporal" not in st.session_state: 
                st.session_state.lote_temporal = []
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                opciones_stock = ["-- NUEVO ARTÍCULO --"] + df_stock["Accesorio"].tolist()
                prod_sel = c1.selectbox("Artículo:", opciones_stock, key="sel_prod_lote")
                cant_ingreso = c2.number_input("Cantidad:", min_value=0, value=0, key="cant_lote")
                costo_ingreso = c3.number_input("Costo Unitario $:", min_value=0.0, step=0.1, key="costo_lote")

                if prod_sel == "-- NUEVO ARTÍCULO --":
                    cn1, cn2, cn3 = st.columns(3)
                    nombre_nuevo = cn1.text_input("Nombre:", key="n_n_l")
                    rubro_nuevo = cn2.text_input("Rubro:", key="r_n_l")
                    prov_nuevo = cn3.text_input("Proveedor:", key="p_n_l")
                
                if st.button("➕ AGREGAR AL LISTADO", use_container_width=True):
                    nombre_final = nombre_nuevo if prod_sel == "-- NUEVO ARTÍCULO --" else prod_sel
                    if nombre_final and cant_ingreso > 0:
                        item_ex = df_stock[df_stock["Accesorio"] == nombre_final]
                        nuevo_i = {
                            "Rubro": rubro_nuevo if prod_sel == "-- NUEVO ARTÍCULO --" else item_ex["Rubro"].values[0],
                            "Proveedor": prov_nuevo if prod_sel == "-- NUEVO ARTÍCULO --" else item_ex["Proveedor"].values[0],
                            "Accesorio": nombre_final, "Stock": cant_ingreso, "Costo Base": costo_ingreso,
                            "Flete": item_ex["Flete"].values[0] if not item_ex.empty else 0.0,
                            "% Ganancia": item_ex["% Ganancia"].values[0] if not item_ex.empty else 40.0,
                            "Descripcion": item_ex["Descripcion"].values[0] if not item_ex.empty else ""
                        }
                        st.session_state.lote_temporal.append(nuevo_i)
                        st.rerun()

            if st.session_state.lote_temporal:
                df_temp = pd.DataFrame(st.session_state.lote_temporal)
                lote_final_edit = st.data_editor(df_temp, use_container_width=True, key="ed_lote_vis")
                
                col_acc1, col_acc2 = st.columns(2)
                if col_acc1.button("🗑️ LIMPIAR LISTA", use_container_width=True):
                    st.session_state.lote_temporal = []
                    st.rerun()
                    
                if col_acc2.button("🚀 CONFIRMAR E INGRESAR", type="primary", use_container_width=True):
                    detalle_hist = []; inv_total = 0
                    for _, r in lote_final_edit.iterrows():
                        n, stk, cb, fl, ga = r["Accesorio"], r["Stock"], r["Costo Base"], r["Flete"], r["% Ganancia"]
                        l1 = round((cb + fl) * (1 + ga/100), 2)
                        l2 = round(l1 * 0.90, 2)
                        inv_total += (stk * cb)
                        detalle_hist.append(f"{stk}x {n} (${cb})")
                        mask = df_stock["Accesorio"] == n
                        if mask.any():
                            df_stock.loc[mask, "Stock"] += stk
                            df_stock.loc[mask, ["Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]] = [cb, fl, ga, l1, l2]
                        else:
                            nf = pd.DataFrame([{"Rubro": r["Rubro"], "Proveedor": r["Proveedor"], "Accesorio": n, "Stock": stk, "Costo Base": cb, "Flete": fl, "% Ganancia": ga, "Lista 1 (Cheques)": l1, "Lista 2 (Efectivo)": l2, "Descripcion": r["Descripcion"]}])
                            df_stock = pd.concat([df_stock, nf], ignore_index=True)
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    n_h = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Articulos": " | ".join(detalle_hist), "Costo Total Compra": round(inv_total, 2)}])
                    pd.concat([df_lotes_historial, n_h], ignore_index=True).to_csv(ARCHIVO_REGISTRO_LOTES, index=False)
                    st.session_state.lote_temporal = []
                    st.success("✅ Stock e Historial actualizados.")
                    st.rerun()

    with tabs[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="ed_maestro_full")
        if st.button("Guardar Cambios Maestro"):
            df_ed["Lista 1 (Cheques)"] = ((df_ed["Costo Base"] + df_ed["Flete"]) * (1 + df_ed["% Ganancia"] / 100)).round(2)
            df_ed["Lista 2 (Efectivo)"] = (df_ed["Lista 1 (Cheques)"] * 0.90).round(2)
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("✅ Base actualizada"); st.rerun()
        
        with st.expander("🗑️ ZONA DE PELIGRO - ELIMINAR"):
            art_borrar = st.selectbox("Seleccionar para borrar:", [""] + df_stock["Accesorio"].tolist(), key="del_item_sel")
            
            if art_borrar != "":
                st.error(f"¿Estás seguro de borrar **{art_borrar}**?")
                
                # Usamos una columna para centrar el botón o darle aire
                c_del, _ = st.columns([1, 2])
                
                # El truco es que el botón ejecute la lógica y luego fuerce el rerun
                if c_del.button("⚠️ CONFIRMAR ELIMINACIÓN", type="primary", use_container_width=True):
                    # 1. Filtrar el DataFrame
                    df_stock = df_stock[df_stock["Accesorio"] != art_borrar]
                    
                    # 2. Guardar el archivo inmediatamente
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    
                    # 3. Mostrar mensaje de éxito y limpiar el estado
                    st.success(f"🔥 '{art_borrar}' eliminado correctamente.")
                    
                    # 4. Esperar un instante y recargar
                    st.rerun()
    with tabs[3]: # CTA CTE
        st.header("👥 Gestión de Cuentas Corrientes")
        if not df_clientes.empty:
            cli_sel = st.selectbox("🔍 Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="busqueda_global_cli")
            idx_c = df_clientes[df_clientes["Nombre"] == cli_sel].index[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Saldo", formatear_moneda(df_clientes.at[idx_c, "Saldo"]))
            c2.write(f"📞 {df_clientes.at[idx_c, 'Tel']} | 📍 {df_clientes.at[idx_c, 'Localidad']}")
            c3.write(f"🏠 {df_clientes.at[idx_c, 'Direccion']}")
            st.divider()
            
            col_m, col_o = st.columns([2, 1])
            with col_m:
                st.subheader("Historial")
                hist = df_movs[df_movs["Cliente"] == cli_sel].sort_index(ascending=False)
                for i, row in hist.iterrows():
                    color = "🔴" if row["Tipo"] == "VENTA" else "🟢" if row["Tipo"] == "PAGO" else "🔵"
                    with st.expander(f"{color} {row['Fecha']} | {row['Tipo']} | {formatear_moneda(row['Monto'])}"):
                        st.write(f"**Detalle:** {row['Detalle']}")
            with col_o:
                st.subheader("Registrar Pago")
                m_p = st.number_input("Monto $:", min_value=0.0, key="pago_m_i")
                if st.button("Confirmar Pago"):
                    df_clientes.at[idx_c, "Saldo"] = round(df_clientes.at[idx_c, "Saldo"] - m_p, 2)
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    n_m = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_sel, "Tipo": "PAGO", "Monto": m_p, "Metodo": "Efectivo", "Detalle": "Pago registrado"}])
                    pd.concat([df_movs, n_m], ignore_index=True).to_csv(ARCHIVO_MOVIMIENTOS, index=False); st.rerun()

    with tabs[4]: # PRESUPUESTADOR (AQUÍ SE CORRIGIÓ NOTA DE CRÉDITO)
        st.header("📄 Generador de Presupuestos")
        cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cliente_presupuesto_unico")
        p1, p2, p3 = st.columns([2, 1, 1])
        with p1: i_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist(), key="item_presupuesto_unico")
        with p2: q_p = st.number_input("Cant:", min_value=1, value=1, key="cant_presupuesto_unico")
        with p3: l_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_presupuesto_unico")
        if st.button("➕ AGREGAR AL CARRITO"):
            p_u = round(df_stock[df_stock["Accesorio"] == i_p][l_p].values[0], 2)
            st.session_state.carrito.append({"Producto": i_p, "Cant": q_p, "Precio U.": p_u, "Subtotal": round(p_u * q_p, 2)})
            st.rerun()
        if st.session_state.carrito:
            st.subheader("Detalle")
            for index, item in enumerate(st.session_state.carrito):
                col_item, col_btn = st.columns([4, 1])
                with col_item: st.write(f"**{item['Cant']}x** {item['Producto']} — {formatear_moneda(item['Subtotal'])}")
                with col_btn:
                    if st.button("❌", key=f"del_item_{index}"): st.session_state.carrito.pop(index); st.rerun()
            t_f = round(sum(item["Subtotal"] for item in st.session_state.carrito), 2)
            st.markdown(f"### TOTAL: {formatear_moneda(t_f)}")
            st.divider()
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                pdf_pre = generar_pdf_binario(cli_p, st.session_state.carrito, t_f, df_clientes, "PRESUPUESTO")
                if pdf_pre: st.download_button("📥 BAJAR PDF", pdf_pre, f"Pre_{cli_p}.pdf", "application/pdf", key="btn_download_pre", use_container_width=True)
            with b2:
                if st.button("✅ ORDEN", use_container_width=True): st.session_state.confirmar_orden = True
            with b3:
                if st.button("🔵 N. CRÉDITO", use_container_width=True): st.session_state.confirmar_nc = True
            with b4:
                if st.button("🗑️ LIMPIAR", use_container_width=True): st.session_state.carrito = []; st.rerun()

            # LÓGICA DE ORDEN (EXISTENTE)
            if st.session_state.confirmar_orden:
                st.warning(f"¿Generar ORDEN para {cli_p}?")
                c_si, c_no = st.columns(2)
                if c_si.button("SÍ, GENERAR"):
                    det_prod = ", ".join([f"{item['Cant']}x {item['Producto']} (á {formatear_moneda(item['Precio U.'])})" for item in st.session_state.carrito])
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] -= item["Cant"]
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    if cli_p != "Consumidor Final":
                        idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                        df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] + t_f, 2)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        n_mov = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "VENTA", "Monto": t_f, "Metodo": "-", "Detalle": det_prod}])
                        pd.concat([df_movs, n_mov]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.session_state.carrito = []; st.session_state.confirmar_orden = False; st.success("Orden procesada"); st.rerun()
                if c_no.button("CANCELAR"): st.session_state.confirmar_orden = False; st.rerun()

            # --- LÓGICA DE NOTA DE CRÉDITO (CORREGIDA) ---
            if st.session_state.confirmar_nc:
                st.info(f"¿Emitir NOTA DE CRÉDITO para {cli_p}? Esto devolverá el stock y restará saldo.")
                nc_si, nc_no = st.columns(2)
                if nc_si.button("SÍ, EMITIR NC"):
                    det_nc = ", ".join([f"{item['Cant']}x {item['Producto']} (Devolución)" for item in st.session_state.carrito])
                    # 1. Devolver Stock
                    for item in st.session_state.carrito:
                        df_stock.loc[df_stock["Accesorio"] == item["Producto"], "Stock"] += item["Cant"]
                    df_stock.to_csv(ARCHIVO_ARTICULOS, index=False)
                    # 2. Restar Saldo al Cliente
                    if cli_p != "Consumidor Final":
                        idx_cp = df_clientes[df_clientes["Nombre"] == cli_p].index[0]
                        df_clientes.at[idx_cp, "Saldo"] = round(df_clientes.at[idx_cp, "Saldo"] - t_f, 2)
                        df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                        # 3. Registrar Movimiento
                        n_mov_nc = pd.DataFrame([{"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": cli_p, "Tipo": "N. CRÉDITO", "Monto": t_f, "Metodo": "-", "Detalle": det_nc}])
                        pd.concat([df_movs, n_mov_nc]).to_csv(ARCHIVO_MOVIMIENTOS, index=False)
                    st.session_state.carrito = []; st.session_state.confirmar_nc = False; st.success("Nota de Crédito aplicada"); st.rerun()
                if nc_no.button("CANCELAR NC"): st.session_state.confirmar_nc = False; st.rerun()

    with tabs[5]: # ÓRDENES
        st.header("📋 Historial Global")
        st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True, hide_index=True)

    with tabs[6]: # CIERRE
        st.header("🏁 Cierre de Caja")
        c1, c2 = st.columns(2)
        v_s = round((df_stock['Stock'] * df_stock['Costo Base']).sum(), 2)
        c1.metric("Valor Stock", formatear_moneda(v_s))
        c2.metric("Deuda Clientes", formatear_moneda(df_clientes['Saldo'].sum()))

    with tabs[7]: # REMITOS
        st.header("📦 Generador de Remitos")
        cli_r = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_remito")
        r1, r2, r3 = st.columns([2, 1, 1])
        with r1: i_r = st.selectbox("Artículo:", df_stock["Accesorio"].tolist(), key="item_remito")
        with r2: q_r = st.number_input("Cant:", min_value=1, value=1, key="cant_remito")
        with r3: l_r = st.selectbox("Lista de Precio:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_remito")
        if st.button("➕ AGREGAR AL REMITO"):
            p_u_r = round(df_stock[df_stock["Accesorio"] == i_r][l_r].values[0], 2)
            st.session_state.remito_items.append({"Producto": i_r, "Cant": q_r, "Precio U.": p_u_r, "Subtotal": round(p_u_r * q_r, 2)})
            st.rerun()
        if st.session_state.remito_items:
            st.table(st.session_state.remito_items)
            t_remito = round(sum(item["Subtotal"] for item in st.session_state.remito_items), 2)
            pdf_remito = generar_pdf_binario(cli_r, st.session_state.remito_items, t_remito, df_clientes, "REMITO")
            if pdf_remito: st.download_button("📥 DESCARGAR REMITO", pdf_remito, f"Remito_{cli_r}.pdf", "application/pdf")
            if st.button("🗑️ LIMPIAR REMITO"): st.session_state.remito_items = []; st.rerun()

st.divider()
with st.expander("🚀 CARGAR BASES DE DATOS AL VOLUMEN"):
    archivo_subido = st.file_uploader("Elegir archivo CSV", type="csv")
    destino = st.selectbox("¿Qué archivo estás subiendo?", [ARCHIVO_ARTICULOS, ARCHIVO_CLIENTES, ARCHIVO_MOVIMIENTOS])
    if st.button("Guardar en Railway"):
        if archivo_subido:
            with open(destino, "wb") as f: f.write(archivo_subido.getbuffer())
            st.success(f"✅ ¡{destino} guardado!"); st.rerun()
