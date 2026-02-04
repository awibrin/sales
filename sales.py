import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import calendar

# Configuration de la page
st.set_page_config(
    page_title="Pilotage Commercial",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Style CSS pour mobile et couleurs
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .positive {
        color: #28a745;
        font-weight: bold;
    }
    .negative {
        color: #dc3545;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== JOURS FÉRIÉS ====================

def get_public_holidays(year):
    """R
