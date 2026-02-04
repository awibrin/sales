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
    """Retourne les jours fériés belges/français/espagnols pour une année"""
    # Jours fériés fixes communs
    holidays = [
        datetime(year, 1, 1),   # Nouvel An
        datetime(year, 5, 1),   # Fête du Travail
        datetime(year, 12, 25), # Noël
        datetime(year, 12, 26), # Lendemain de Noël (BE)
        datetime(year, 11, 1),  # Toussaint
        datetime(year, 11, 11), # Armistice
        datetime(year, 7, 14),  # Fête Nationale FR
        datetime(year, 7, 21),  # Fête Nationale BE
        datetime(year, 8, 15),  # Assomption
    ]
    
    # Pâques et jours mobiles (calcul approximatif - à affiner si besoin)
    # Pour 2025: Pâques = 20 avril
    # Pour 2026: Pâques = 5 avril
    easter_dates = {
        2024: datetime(2024, 3, 31),
        2025: datetime(2025, 4, 20),
        2026: datetime(2026, 4, 5),
        2027: datetime(2027, 3, 28),
    }
    
    if year in easter_dates:
        easter = easter_dates[year]
        holidays.extend([
            easter + timedelta(days=1),   # Lundi de Pâques
            easter + timedelta(days=39),  # Ascension
            easter + timedelta(days=50),  # Lundi de Pentecôte
        ])
    
    return set(holidays)

def is_working_day(date, holidays=None):
    """Vérifie si un jour est ouvrable (pas weekend, pas férié)"""
    if holidays is None:
        holidays = get_public_holidays(date.year)
    
    # Weekend (samedi=5, dimanche=6)
    if date.weekday() >= 5:
        return False
    
    # Jour férié
    if date in holidays:
        return False
    
    return True

def count_working_days(start_date, end_date, holidays=None):
    """Compte le nombre de jours ouvrables entre deux dates (inclus)"""
    if holidays is None:
        holidays = get_public_holidays(start_date.year)
    
    count = 0
    current = start_date
    while current <= end_date:
        if is_working_day(current, holidays):
            count += 1
        current += timedelta(days=1)
    return count

def get_working_days_in_month(year, month):
    """Retourne la liste des jours ouvrables dans un mois"""
    holidays = get_public_holidays(year)
    first_day = datetime(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num)
    
    working_days = []
    current = first_day
    while current <= last_day:
        if is_working_day(current, holidays):
            working_days.append(current)
        current += timedelta(days=1)
    
    return working_days

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
    
    # Table des jours fériés personnalisés (optionnel)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT,
            UNIQUE(date)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Retourne une connexion à la base de données"""
    return sqlite3.connect('commercial_tracking.db')

def get_custom_holidays():
    """Récupère les jours fériés personnalisés de la base"""
    conn = get_db_connection()
    df = pd.read_sql_query('SELECT date FROM custom_holidays', conn)
    conn.close()
    if not df.empty:
        return set(pd.to_datetime(df['date']))
    return set()

def add_custom_holiday(date, description):
    """Ajoute un jour férié personnalisé"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO custom_holidays (date, description)
            VALUES (?, ?)
        ''', (date.strftime('%Y-%m-%d'), description))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

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
    """Récupère les ventes pour une zone et un mois donné"""
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
    """Calcule les données par semaine EN JOURS OUVRABLES"""
    sales_df = get_sales_data(zone, year, month)
    
    if sales_df.empty:
        return pd.DataFrame()
    
    sales_df['week'] = sales_df['date'].apply(get_week_number)
    weekly = sales_df.groupby('week')['volume'].sum().reset_index()
    weekly.columns = ['Semaine', 'Réalisé']
    
    # Calculer l'objectif hebdomadaire basé sur jours ouvrables
    monthly_target = get_monthly_target(zone, year, month)
    working_days_month = get_working_days_in_month(year, month)
    total_working_days = len(working_days_month)
    
    if total_working_days == 0:
        weekly['Target'] = 0
    else:
        weekly_targets = []
        holidays = get_public_holidays(year)
        custom_holidays = get_custom_holidays()
        all_holidays = holidays.union(custom_holidays)
        
        for week_num in weekly['Semaine']:
            # Compter les jours ouvrables dans cette semaine
            week_dates = sales_df[sales_df['week'] == week_num]['date'].unique()
            week_working_days = sum(1 for d in week_dates if is_working_day(pd.Timestamp(d).to_pydatetime(), all_holidays))
            week_target = (monthly_target / total_working_days) * week_working_days
            weekly_targets.append(int(week_target))
        
        weekly['Target'] = weekly_targets
    
    weekly['Delta'] = weekly['Réalisé'] - weekly['Target']
    weekly['Semaine'] = weekly['Semaine'].apply(lambda x: f'W-{x}')
    
    return weekly

def calculate_run_rate(zone, year, month, current_date):
    """Calcule le run-rate dynamique EN JOURS OUVRABLES"""
    monthly_target = get_monthly_target(zone, year, month)
    if monthly_target == 0:
        return 0
    
    # Ventes réalisées jusqu'à aujourd'hui
    sales_df = get_sales_data(zone, year, month)
    realized = sales_df['volume'].sum() if not sales_df.empty else 0
    
    # Jours ouvrables restants (incluant aujourd'hui s'il est ouvrable)
    last_day_num = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day_num)
    
    holidays = get_public_holidays(year)
    custom_holidays = get_custom_holidays()
    all_holidays = holidays.union(custom_holidays)
    
    working_days_remaining = count_working_days(current_date, last_date, all_holidays)
    
    if working_days_remaining <= 0:
        return 0
    
    # Calcul du run-rate nécessaire
    remaining_volume = monthly_target - realized
    run_rate = remaining_volume / working_days_remaining
    
    return max(0, run_rate)  # Ne peut pas être négatif

# ==================== INTERFACE STREAMLIT ====================

def main():
    init_database()
    
    st.title("📊 Pilotage Commercial Intransigeant")
    st.caption("🔵 Calculs basés sur jours ouvrables (hors weekends et jours fériés)")
    
    # Date du jour
    today = datetime.now()
    current_year = today.year
    current_month = today.month
    
    # Onglets principaux
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Dashboard", "✍️ Saisie Ventes", "⚙️ Configuration", "📅 Jours Fériés"])
    
    # ==================== DASHBOARD ====================
    with tab1:
        st.subheader("Tableau de Bord")
        
        # Sélection de zone
        selected_zone = st.selectbox("Sélectionner une zone", get_zones(), key="dashboard_zone")
        
        # Indicateur jour ouvrable
        holidays = get_public_holidays(current_year)
        custom_holidays = get_custom_holidays()
        all_holidays = holidays.union(custom_holidays)
        
        if is_working_day(today, all_holidays):
            st.success("✅ Aujourd'hui est un jour ouvrable")
        else:
            st.warning("⚠️ Aujourd'hui est un weekend ou jour férié")
        
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
        
        # Calcul des jours ouvrables
        working_days_total = len(get_working_days_in_month(current_year, current_month))
        last_day_num = calendar.monthrange(current_year, current_month)[1]
        last_date = datetime(current_year, current_month, last_day_num)
        working_days_left = count_working_days(today, last_date, all_holidays)
        working_days_passed = working_days_total - working_days_left
        
        col_rr1, col_rr2, col_rr3 = st.columns(3)
        with col_rr1:
            st.metric("🔥 Run-Rate Quotidien", f"{run_rate:.1f} ventes/jour")
        with col_rr2:
            st.metric("⏱️ Jours Ouvrables Restants", working_days_left)
        with col_rr3:
            st.metric("📆 Jours Ouvrables Total", f"{working_days_passed}/{working_days_total}")
        
        # Alerte run-rate
        if run_rate > 0 and working_days_passed > 0:
            avg_daily = monthly_realized / working_days_passed
            if run_rate > avg_daily * 1.2:
                st.error(f"🚨 ATTENTION : Le run-rate nécessaire ({run_rate:.1f}) est {((run_rate/avg_daily-1)*100):.0f}% supérieur à votre moyenne actuelle ({avg_daily:.1f})")
            elif run_rate > avg_daily:
                st.warning(f"⚠️ Le run-rate nécessaire ({run_rate:.1f}) est supérieur à votre moyenne ({avg_daily:.1f})")
            else:
                st.success(f"✅ Objectif atteignable : continuez au rythme actuel de {avg_daily:.1f} ventes/jour")
        
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
            'Indicateur': ['Target', 'Réalisé', 'Delta', 'Taux de Réalisation', 'Jours Ouvrables'],
            'Valeur': [
                f"{monthly_target:,}",
                f"{monthly_realized:,}",
                f"{monthly_delta:+,}",
                f"{(monthly_realized/monthly_target*100):.1f}%" if monthly_target > 0 else "N/A",
                f"{working_days_passed}/{working_days_total}"
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
            
            # Vérifier si c'est un jour ouvrable
            sale_datetime = datetime.combine(sale_date, datetime.min.time())
            if not is_working_day(sale_datetime, all_holidays):
                st.warning("⚠️ Ce jour est un weekend ou un jour férié")
        
        if st.button("💾 Enregistrer", type="primary", use_container_width=True):
            if sale_volume >= 0:
                sale_datetime = datetime.combine(sale_date, datetime.min.time())
                if save_sale(sale_zone, sale_datetime, sale_volume):
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
        
        # Afficher le nombre de jours ouvrables du mois sélectionné
        selected_working_days = len(get_working_days_in_month(target_year, target_month))
        st.info(f"ℹ️ Ce mois compte {selected_working_days} jours ouvrables")
        
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
    
    # ==================== JOURS FÉRIÉS ====================
    with tab4:
        st.subheader("📅 Gestion des Jours Fériés")
        
        st.markdown("### 🎉 Jours Fériés Standards")
        st.info("""
        Jours fériés inclus automatiquement :
        - 1er janvier (Nouvel An)
        - Lundi de Pâques
        - 1er mai (Fête du Travail)
        - Ascension
        - Lundi de Pentecôte
        - 14 juillet (Fête Nationale FR)
        - 21 juillet (Fête Nationale BE)
        - 15 août (Assomption)
        - 1er novembre (Toussaint)
        - 11 novembre (Armistice)
        - 25 décembre (Noël)
        - 26 décembre (Lendemain Noël - BE)
        """)
        
        st.markdown("---")
        st.markdown("### ➕ Ajouter un Jour Férié Personnalisé")
        st.caption("Par exemple : fermeture annuelle, pont, événement exceptionnel...")
        
        col1, col2 = st.columns(2)
        with col1:
            custom_holiday_date = st.date_input("Date du jour férié", value=today)
        with col2:
            custom_holiday_desc = st.text_input("Description", placeholder="Ex: Fermeture annuelle")
        
        if st.button("➕ Ajouter", type="primary"):
            custom_datetime = datetime.combine(custom_holiday_date, datetime.min.time())
            if add_custom_holiday(custom_datetime, custom_holiday_desc):
                st.success(f"✅ Jour férié ajouté : {custom_holiday_date.strftime('%d/%m/%Y')}")
                st.rerun()
            else:
                st.error("Ce jour férié existe déjà")
        
        # Liste des jours fériés personnalisés
        st.markdown("---")
        st.markdown("### 📋 Jours Fériés Personnalisés")
        
        conn = get_db_connection()
        custom_holidays_df = pd.read_sql_query('''
            SELECT date as Date, description as Description
            FROM custom_holidays
            ORDER BY date DESC
        ''', conn)
        conn.close()
        
        if not custom_holidays_df.empty:
            custom_holidays_df['Date'] = pd.to_datetime(custom_holidays_df['Date']).dt.strftime('%d/%m/%Y')
            st.dataframe(custom_holidays_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun jour férié personnalisé")
        
        # Calendrier du mois
        st.markdown("---")
        st.markdown("### 📆 Calendrier du Mois en Cours")
        
        working_days_list = get_working_days_in_month(current_year, current_month)
        
        cal_col1, cal_col2 = st.columns(2)
        with cal_col1:
            st.metric("Jours Ouvrables", len(working_days_list))
        with cal_col2:
            total_days = calendar.monthrange(current_year, current_month)[1]
            st.metric("Jours Non-Ouvrables", total_days - len(working_days_list))
        
        # Afficher le calendrier
        first_day = datetime(current_year, current_month, 1)
        last_day = datetime(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
        
        cal_data = []
        current = first_day
        while current <= last_day:
            is_working = is_working_day(current, all_holidays)
            day_type = "✅ Ouvrable" if is_working else "❌ Non-ouvrable"
            cal_data.append({
                'Date': current.strftime('%d/%m/%Y'),
                'Jour': current.strftime('%A'),
                'Type': day_type
            })
            current += timedelta(days=1)
        
        cal_df = pd.DataFrame(cal_data)
        st.dataframe(cal_df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
