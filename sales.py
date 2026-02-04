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

# ==================== BASE DE DONNÉES ====================

def init_database():
    """Initialise la base de données SQLite avec les tables nécessaires"""
    conn = sqlite3.connect('commercial_tracking.db')
    cursor = conn.cursor()
    
    # Table des ventes quotidiennes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT NOT NULL,
            date TEXT NOT NULL,
            volume INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(zone, date)
        )
    ''')
    
    # Table des objectifs mensuels
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            target INTEGER NOT NULL,
            UNIQUE(zone, year, month)
        )
    ''')
    
    # Table du YTD initial (Janvier manuel)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ytd_init (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT NOT NULL,
            year INTEGER NOT NULL,
            january_volume INTEGER NOT NULL,
            UNIQUE(zone, year)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Retourne une connexion à la base de données"""
    return sqlite3.connect('commercial_tracking.db')

# ==================== FONCTIONS MÉTIER ====================

def get_zones():
    """Retourne la liste complète des zones"""
    filiales = ["BEFR", "BENL", "France", "Espagne"]
    concessions = ["Sud-Rhône", "Hauts-de-France", "Luxembourg"]
    return filiales + concessions

def save_sale(zone, date, volume):
    """Enregistre ou met à jour une vente quotidienne"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO sales (zone, date, volume)
            VALUES (?, ?, ?)
            ON CONFLICT(zone, date) DO UPDATE SET volume=excluded.volume
        ''', (zone, date.strftime('%Y-%m-%d'), volume))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'enregistrement : {e}")
        return False
    finally:
        conn.close()

def save_monthly_target(zone, year, month, target):
    """Enregistre l'objectif mensuel pour une zone"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO monthly_targets (zone, year, month, target)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(zone, year, month) DO UPDATE SET target=excluded.target
        ''', (zone, year, month, target))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur : {e}")
        return False
    finally:
        conn.close()

def save_ytd_init(zone, year, january_volume):
    """Enregistre le volume de janvier initial"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ytd_init (zone, year, january_volume)
            VALUES (?, ?, ?)
            ON CONFLICT(zone, year) DO UPDATE SET january_volume=excluded.january_volume
        ''', (zone, year, january_volume))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erreur : {e}")
        return False
    finally:
        conn.close()

def get_sales_data(zone, year, month):
    """Récupère les ventes d'une zone pour un mois donné"""
    conn = get_db_connection()
    query = '''
        SELECT date, volume 
        FROM sales 
        WHERE zone = ? 
        AND strftime('%Y', date) = ? 
        AND strftime('%m', date) = ?
        ORDER BY date
    '''
    df = pd.read_sql_query(query, conn, params=(zone, str(year), f'{month:02d}'))
    conn.close()
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

def get_monthly_target(zone, year, month):
    """Récupère l'objectif mensuel"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT target FROM monthly_targets
        WHERE zone = ? AND year = ? AND month = ?
    ''', (zone, year, month))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_ytd_init(zone, year):
    """Récupère le volume de janvier initial"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT january_volume FROM ytd_init
        WHERE zone = ? AND year = ?
    ''', (zone, year))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def calculate_ytd(zone, current_date):
    """Calcule le YTD : Janvier manuel + cumul depuis février"""
    year = current_date.year
    january_init = get_ytd_init(zone, year)
    
    # Cumul depuis février
    conn = get_db_connection()
    query = '''
        SELECT COALESCE(SUM(volume), 0) as total
        FROM sales
        WHERE zone = ? 
        AND strftime('%Y', date) = ?
        AND strftime('%m', date) >= '02'
        AND date <= ?
    '''
    df = pd.read_sql_query(query, conn, params=(zone, str(year), current_date.strftime('%Y-%m-%d')))
    conn.close()
    
    cumul_from_feb = df['total'].iloc[0] if not df.empty else 0
    return january_init + cumul_from_feb

def get_week_number(date):
    """Retourne le numéro de semaine dans le mois (W-1, W-2, etc.)"""
    first_day = date.replace(day=1)
    days_from_start = (date - first_day).days
    return (days_from_start // 7) + 1

def calculate_weekly_data(zone, year, month):
    """Calcule les données par semaine"""
    sales_df = get_sales_data(zone, year, month)
    
    if sales_df.empty:
        return pd.DataFrame()
    
    sales_df['week'] = sales_df['date'].apply(get_week_number)
    weekly = sales_df.groupby('week')['volume'].sum().reset_index()
    weekly.columns = ['Semaine', 'Réalisé']
    
    # Calculer l'objectif hebdomadaire (proportionnel)
    monthly_target = get_monthly_target(zone, year, month)
    num_days_in_month = calendar.monthrange(year, month)[1]
    
    weekly_targets = []
    for week_num in weekly['Semaine']:
        # Calculer le nombre de jours dans cette semaine
        week_days = sales_df[sales_df['week'] == week_num]['date'].nunique()
        week_target = (monthly_target / num_days_in_month) * week_days
        weekly_targets.append(int(week_target))
    
    weekly['Target'] = weekly_targets
    weekly['Delta'] = weekly['Réalisé'] - weekly['Target']
    weekly['Semaine'] = weekly['Semaine'].apply(lambda x: f'W-{x}')
    
    return weekly

def calculate_run_rate(zone, year, month, current_date):
    """Calcule le run-rate dynamique intransigeant"""
    monthly_target = get_monthly_target(zone, year, month)
    if monthly_target == 0:
        return 0
    
    # Ventes réalisées jusqu'à aujourd'hui
    sales_df = get_sales_data(zone, year, month)
    realized = sales_df['volume'].sum() if not sales_df.empty else 0
    
    # Jours restants (incluant aujourd'hui)
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    days_remaining = (last_date - current_date).days + 1
    
    if days_remaining <= 0:
        return 0
    
    # Calcul du run-rate nécessaire
    remaining_volume = monthly_target - realized
    run_rate = remaining_volume / days_remaining
    
    return max(0, run_rate)  # Ne peut pas être négatif

# ==================== INTERFACE STREAMLIT ====================

def main():
    init_database()
    
    st.title("📊 Pilotage Commercial Intransigeant")
    
    # Date du jour
    today = datetime.now()
    current_year = today.year
    current_month = today.month
    
    # Onglets principaux
    tab1, tab2, tab3 = st.tabs(["📈 Dashboard", "✍️ Saisie Ventes", "⚙️ Configuration"])
    
    # ==================== DASHBOARD ====================
    with tab1:
        st.subheader("Tableau de Bord")
        
        # Sélection de zone
        selected_zone = st.selectbox("Sélectionner une zone", get_zones(), key="dashboard_zone")
        
        # Métriques clés
        col1, col2, col3 = st.columns(3)
        
        monthly_target = get_monthly_target(selected_zone, current_year, current_month)
        sales_df = get_sales_data(selected_zone, current_year, current_month)
        monthly_realized = sales_df['volume'].sum() if not sales_df.empty else 0
        monthly_delta = monthly_realized - monthly_target
        
        with col1:
            st.metric("🎯 Target Mensuel", f"{monthly_target:,}")
        with col2:
            delta_color = "normal" if monthly_delta >= 0 else "inverse"
            st.metric("✅ Réalisé", f"{monthly_realized:,}", delta=f"{monthly_delta:+,}", delta_color=delta_color)
        with col3:
            ytd = calculate_ytd(selected_zone, today)
            st.metric("📅 YTD", f"{ytd:,}")
        
        # Run-Rate Dynamique
        st.markdown("---")
        run_rate = calculate_run_rate(selected_zone, current_year, current_month, today)
        
        col_rr1, col_rr2 = st.columns(2)
        with col_rr1:
            st.metric("🔥 Run-Rate Quotidien Nécessaire", f"{run_rate:.1f}")
        with col_rr2:
            last_day = calendar.monthrange(current_year, current_month)[1]
            days_left = (datetime(current_year, current_month, last_day) - today).days + 1
            st.metric("⏱️ Jours Restants", days_left)
        
        # Données hebdomadaires
        st.markdown("---")
        st.subheader("📊 Performance Hebdomadaire")
        
        weekly_df = calculate_weekly_data(selected_zone, current_year, current_month)
        
        if not weekly_df.empty:
            # Affichage avec couleurs
            def color_delta(val):
                color = '#28a745' if val >= 0 else '#dc3545'
                return f'color: {color}; font-weight: bold'
            
            styled_weekly = weekly_df.style.applymap(color_delta, subset=['Delta'])
            st.dataframe(styled_weekly, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune donnée hebdomadaire disponible")
        
        # Résumé mensuel
        st.markdown("---")
        st.subheader("📅 Résumé Mensuel")
        
        monthly_summary = pd.DataFrame({
            'Indicateur': ['Target', 'Réalisé', 'Delta', 'Taux de Réalisation'],
            'Valeur': [
                f"{monthly_target:,}",
                f"{monthly_realized:,}",
                f"{monthly_delta:+,}",
                f"{(monthly_realized/monthly_target*100):.1f}%" if monthly_target > 0 else "N/A"
            ]
        })
        
        st.dataframe(monthly_summary, use_container_width=True, hide_index=True)
    
    # ==================== SAISIE VENTES ====================
    with tab2:
        st.subheader("✍️ Saisie des Ventes Quotidiennes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            sale_zone = st.selectbox("Zone", get_zones(), key="sale_zone")
            sale_date = st.date_input("Date", value=today, max_value=today)
        
        with col2:
            sale_volume = st.number_input("Volume de ventes", min_value=0, step=1)
        
        if st.button("💾 Enregistrer", type="primary", use_container_width=True):
            if sale_volume >= 0:
                if save_sale(sale_zone, sale_date, sale_volume):
                    st.success(f"✅ {sale_volume} ventes enregistrées pour {sale_zone} le {sale_date.strftime('%d/%m/%Y')}")
                    st.rerun()
            else:
                st.error("Le volume doit être positif")
        
        # Historique des saisies récentes
        st.markdown("---")
        st.subheader("📜 Historique Récent")
        
        conn = get_db_connection()
        recent_sales = pd.read_sql_query('''
            SELECT zone as Zone, date as Date, volume as Volume
            FROM sales
            ORDER BY date DESC, zone
            LIMIT 20
        ''', conn)
        conn.close()
        
        if not recent_sales.empty:
            recent_sales['Date'] = pd.to_datetime(recent_sales['Date']).dt.strftime('%d/%m/%Y')
            st.dataframe(recent_sales, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune vente enregistrée")
    
    # ==================== CONFIGURATION ====================
    with tab3:
        st.subheader("⚙️ Configuration des Objectifs")
        
        # Targets mensuels
        st.markdown("### 🎯 Objectifs Mensuels")
        
        config_zone = st.selectbox("Zone", get_zones(), key="config_zone")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            target_year = st.number_input("Année", min_value=2024, max_value=2030, value=current_year)
        with col2:
            target_month = st.number_input("Mois", min_value=1, max_value=12, value=current_month)
        with col3:
            target_value = st.number_input("Objectif", min_value=0, step=10)
        
        if st.button("💾 Enregistrer Target", type="primary"):
            if save_monthly_target(config_zone, target_year, target_month, target_value):
                st.success(f"✅ Objectif de {target_value:,} enregistré pour {config_zone}")
                st.rerun()
        
        # YTD Initial (Janvier)
        st.markdown("---")
        st.markdown("### 📅 Initialisation YTD (Janvier Manuel)")
        
        col1, col2 = st.columns(2)
        with col1:
            ytd_zone = st.selectbox("Zone", get_zones(), key="ytd_zone")
            ytd_year = st.number_input("Année", min_value=2024, max_value=2030, value=current_year, key="ytd_year")
        with col2:
            ytd_volume = st.number_input("Volume Janvier", min_value=0, step=10)
        
        if st.button("💾 Enregistrer YTD Initial", type="primary"):
            if save_ytd_init(ytd_zone, ytd_year, ytd_volume):
                st.success(f"✅ Volume de janvier ({ytd_volume:,}) enregistré pour {ytd_zone}")
                st.rerun()
        
        # Vue d'ensemble des targets
        st.markdown("---")
        st.markdown("### 📊 Vue d'Ensemble des Targets")
        
        conn = get_db_connection()
        all_targets = pd.read_sql_query('''
            SELECT zone as Zone, year as Année, month as Mois, target as Objectif
            FROM monthly_targets
            ORDER BY year DESC, month DESC, zone
        ''', conn)
        conn.close()
        
        if not all_targets.empty:
            all_targets['Mois'] = all_targets['Mois'].apply(lambda x: f"{x:02d}")
            st.dataframe(all_targets, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun objectif configuré")

if __name__ == "__main__":
    main()
