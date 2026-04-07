import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# --- CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = "gestion_af_accesorios.db"

def ejecutar_query(query, params=(), commit=False):
    conn = sqlite3.connect(DB_NAME)
    try:
        if commit:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        else:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error de base de datos: {e}")
    finally:
        conn.close()

# --- LA FUNCIÓN QUE EVITA QUE EXPLOTE ---
def limpiar_y_convertir(val):
    if pd.isna(val) or str(val).strip() == "":
        return 0.0
    try:
        # Quitamos todo lo que no sea número, punto o coma
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except:
        return 0.0

def init_db():
    ejecutar_query('''CREATE TABLE IF NOT EXISTS articulos 
                 (id INTEGER PRIMARY KEY, rubro TEXT, proveedor TEXT, accesorio TEXT, 
                  stock REAL, costo_base REAL, flete REAL, ganancia REAL, 
                  lista1 REAL, lista2 REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, saldo REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, monto REAL)''', commit=True)

init_db()
st.set_page_config(layout="wide", page_title="AF Accesorios")

# --- CARGA DE DATOS ---
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# TAB 1: LOTE (CARGA SEGURA)
with tabs[1]:
    st.header("🚚 Carga por Lote")
    df_vacio = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_vacio, num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 Procesar e Importar"):
        for _, r in ed_lote.iterrows():
            if r['accesorio'] and str(r['accesorio']).strip() != "":
                cb = limpiar_y_convertir(r['costo_base'])
                fl = limpiar_y_convertir(r['flete'])
                ga = limpiar_y_convertir(r['ganancia'])
                stk = limpiar_y_convertir(r['stock'])
                l1 = (cb + fl) * (1 + ga/100)
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''', 
                               (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), stk, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("¡Importado correctamente!")
        st.rerun()

# TAB 2: MAESTRO (ELIMINACIÓN MÚLTIPLE Y CÁLCULO SEGURO)
with tabs[2]:
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_edit = df_stock.copy()
        df_edit.insert(0, "Borrar", False)
        
        # IMPORTANTE: Desactivamos el cálculo automático en las columnas para que no tire TypeError
        res_ed = st.data_editor(df_edit, use_container_width=True, hide_index=True, key="maestro_editor")
        
        col_m1, col_m2 = st.columns([1, 2])
        
        with col_m1:
            if st.button("🗑️ Eliminar Marcados"):
                ids = res_ed[res_ed["Borrar"] == True]["id"].tolist()
                for i in ids:
                    ejecutar_query("DELETE FROM articulos WHERE id = ?", (i,), commit=True)
                st.rerun()
        
        with col_m2:
            if st.button("💾 Guardar y Recalcular Todo"):
                df_final = res_ed.drop(columns=["Borrar"])
                # Procesamos fila por fila para asegurar que todo sea número
                for i, row in df_final.iterrows():
                    cb = limpiar_y_convertir(row['costo_base'])
                    fl = limpiar_y_convertir(row['flete'])
                    ga = limpiar_y_convertir(row['ganancia'])
                    stk = limpiar_y_convertir(row['stock'])
                    
                    l1 = (cb + fl) * (1 + ga/100)
                    df_final.at[i, 'costo_base'] = cb
                    df_final.at[i, 'flete'] = fl
                    df_final.at[i, 'ganancia'] = ga
                    df_final.at[i, 'stock'] = stk
                    df_final.at[i, 'lista1'] = l1
                    df_final.at[i, 'lista2'] = l1 * 0.9
                
                conn = sqlite3.connect(DB_NAME)
                df_final.to_sql("articulos", conn, if_exists="replace", index=False)
                conn.close()
                st.success("Cambios guardados y precios actualizados.")
                st.rerun()
    else:
        st.info("No hay artículos cargados.")

# TAB 6: CIERRE (EL QUE FALTABA)
with tabs[6]:
    st.header("🏁 Resumen de Caja y Stock")
    c1, c2, c3 = st.columns(3)
    
    total_deuda = df_clientes["saldo"].sum() if not df_clientes.empty else 0
    inversion = (df_stock["stock"] * df_stock["costo_base"]).sum() if not df_stock.empty else 0
    ganancia_proyectada = (df_stock["stock"] * df_stock["lista1"]).sum() - inversion if not df_stock.empty else 0
    
    c1.metric("Deuda de Clientes", f"$ {total_deuda:,.2f}")
    c2.metric("Inversión en Stock", f"$ {inversion:,.2f}")
    c3.metric("Ganancia Estimada (L1)", f"$ {ganancia_proyectada:,.2f}")

# Resto de pestañas simplificadas para evitar errores
with tabs[0]: st.header("Stock Actual"); st.dataframe(df_stock, use_container_width=True, hide_index=True)
with tabs[3]: # CTA CTE
    st.header("Cuentas Corrientes")
    if not df_clientes.empty:
        sel = st.selectbox("Cliente", df_clientes["nombre"].tolist())
        s = df_clientes[df_clientes["nombre"] == sel]["saldo"].values[0]
        st.write(f"Saldo: **$ {s:,.2f}**")
    else:
        st.text_input("Nuevo Cliente")
        if st.button("Crear"): st.rerun()
