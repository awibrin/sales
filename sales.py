import streamlit as st
import pandas as pd
import plotly.express as px

# Configuration
st.set_page_config(page_title="Suivi Intransigeant Ventes", layout="wide")

# --- CHARGEMENT & NETTOYAGE (Basé sur ton Excel) ---
@st.cache_data
def load_data():
    # Ici on utilise les données nettoyées depuis ton Excel
    df_summary = pd.read_csv('sales_summary.csv')
    df_daily = pd.read_csv('sales_cleaned.csv')
    return df_summary, df_daily

df_summary, df_daily = load_data()

# --- HEADER ---
st.title("🚀 Sales Performance Tracking - Février 2026")
st.markdown("---")

# --- SECTION 1 : KPIs GLOBAUX ---
total_realise = df_summary['Total_Réalisé'].sum()
total_target = df_summary['Total_Target'].sum()
global_achievement = (total_realise / total_target * 100) if total_target > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("Réalisé Total", f"{total_realise:,.0f} units", delta=None)
col2.metric("Objectif Total", f"{total_target:,.0f} units")
col3.metric("% Achievement", f"{global_achievement:.1f}%", delta=f"{total_realise - total_target:,.0f} vs Target", delta_color="inverse")

st.markdown("---")

# --- SECTION 2 : PERFORMANCE PAR ENTITÉ ---
st.subheader("📊 Performance par Filiale & Concession")

# Ajout d'une barre de progression visuelle dans le tableau
def color_achievement(val):
    color = 'red' if val < 50 else 'orange' if val < 85 else 'green'
    return f'color: {color}; font-weight: bold'

# Affichage du tableau de bord
st.dataframe(
    df_summary.style.applymap(color_achievement, subset=['Completion_%']),
    use_container_width=True
)

# --- SECTION 3 : TENDANCE QUOTIDIENNE ---
st.subheader("📈 Évolution des Ventes Journalières")
daily_trend = df_daily.groupby('Date')['Sales'].sum().reset_index()
fig = px.line(daily_trend, x='Date', y='Sales', title="Ventes cumulées vs Temps", markers=True)
st.plotly_chart(fig, use_container_width=True)

# --- FOCUS SUR LES "LAGGARDS" (Ceux qui sont en retard) ---
st.error("⚠️ Zones en alerte (Achievement < 10%)")
low_perf = df_summary[df_summary['Completion_%'] < 10]
st.table(low_perf[['Entity', 'Total_Réalisé', 'Total_Target', 'Delta']])
