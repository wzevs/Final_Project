import streamlit as st
import pandas as pd
import os
import sqlite3
import streamlit_authenticator as stauth
from database.database_manager import DatabaseManager
from services.product_service import ProductService
from api_clients.gitec_client import GitecClient
from dotenv import load_dotenv

# 1. საწყისი კონფიგურაცია
load_dotenv()
st.set_page_config(page_title="Inventory Manager", layout="wide", page_icon="🖥️")
db = DatabaseManager()
db.create_user_table()  # ქმნის ცხრილს, თუ არ არსებობს


# 2. ფუნქცია მომხმარებლების ბაზიდან წამოსაღებად
def load_users_from_db():
    try:
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        users = conn.execute("SELECT * FROM users").fetchall()
        conn.close()

        user_dict = {'usernames': {}}
        for u in users:
            user_dict['usernames'][u['username']] = {
                'email': u['email'],
                'name': u['name'],
                'password': u['password']
            }
        return user_dict
    except Exception:
        return {'usernames': {}}


# 3. ავტორიზაციის მომზადება (სესიაში შენახვით)
if 'credentials' not in st.session_state or st.session_state.get('reload_users'):
    st.session_state['credentials'] = load_users_from_db()
    st.session_state['reload_users'] = False

authenticator = stauth.Authenticate(
    st.session_state['credentials'],
    'inventory_cookie',
    'signature_key_123',
    30
)

# --- CSS სტილი (Dark Mode) ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {
        background-color: #1a1d24;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border: 1px solid #36393f;
    }
    div[data-testid="stMetricValue"] { color: #ffffff !important; font-size: 2.5rem !important; font-weight: 700 !important; }
    div[data-testid="stMetricLabel"] { color: rgba(255, 255, 255, 0.8) !important; font-size: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

# 4. ავტორიზაციის და რეგისტრაციის ბლოკი
if not st.session_state.get('authentication_status'):
    tab_login, tab_reg = st.tabs(["🔑 შესვლა", "📝 რეგისტრაცია"])

    with tab_login:
        authenticator.login(location='main')
        if st.session_state.get('authentication_status') == False:
            st.error('მომხმარებლის სახელი ან პაროლი არასწორია')
        elif st.session_state.get('authentication_status') is None:
            st.info('გთხოვთ შეიყვანოთ მონაცემები')

    with tab_reg:
        try:
            # რეგისტრაციის ფორმა
            if authenticator.register_user(location='main'):
                # მონაცემების უსაფრთხოდ ამოღება სესიიდან
                current_users = st.session_state['credentials'].get('usernames', {})

                if current_users:
                    # ვიღებთ ბოლო დამატებულ იუზერნეიმს
                    new_username = list(current_users.keys())[-1]
                    user_data = current_users[new_username]

                    # ვიყენებთ .get() შეცდომების თავიდან ასაცილებლად
                    u_email = user_data.get('email', '')
                    u_name = user_data.get('name', new_username)
                    u_pass = user_data.get('password', '')

                    # შენახვა SQLite-ში
                    if db.add_user(new_username, u_email, u_name, u_pass):
                        st.success('რეგისტრაცია წარმატებულია! გადადით "შესვლის" ტაბზე.')
                        st.session_state['reload_users'] = True
                        st.rerun()
                    else:
                        st.error('ეს მომხმარებელი უკვე არსებობს.')
        except Exception as e:
            st.error(f"რეგისტრაციის შეცდომა: {e}")

# 5. მთავარი კონტენტი (ავტორიზებულებისთვის)
if st.session_state.get('authentication_status'):

    with st.sidebar:
        st.write(f"👋 მომხმარებელი: **{st.session_state['name']}**")
        authenticator.logout(location='sidebar')
        st.divider()
        st.header("🔍 ფილტრაცია")

    st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი")


    @st.cache_data(ttl=600)
    def load_and_sync_data():
        try:
            service = ProductService(db_manager=db)
            data_path = "data/distributor_files/"
            if os.path.exists(data_path):
                with st.spinner('ფაილების სინქრონიზაცია...'):
                    service.import_all_from_folder(data_path)

            with st.spinner('API სინქრონიზაცია...'):
                gitec = GitecClient()
                gitec_prods = gitec.fetch_products()
                if gitec_prods:
                    db.save_products(gitec_prods, "gitec")

            conn = sqlite3.connect(db.db_path)
            query = "SELECT distributor, name, category, price, quantity FROM products"
            df_result = pd.read_sql_query(query, conn)
            conn.close()

            df_result.columns = ["მომწოდებელი", "დასახელება", "კატეგორია", "ფასი (₾)", "რაოდენობა"]
            return df_result
        except Exception as e:
            st.error(f"შეცდომა: {e}")
            return pd.DataFrame()


    df = load_and_sync_data()

    if not df.empty:
        # ფილტრები
        selected_brand = st.sidebar.multiselect("მომწოდებელი:", options=df["მომწოდებელი"].unique(),
                                                default=df["მომწოდებელი"].unique())
        selected_cat = st.sidebar.multiselect("კატეგორია:", options=df["კატეგორია"].unique(),
                                              default=df["კატეგორია"].unique())
        search_query = st.text_input("მოძებნე პროდუქტი:", "")

        mask = (df["მომწოდებელი"].isin(selected_brand)) & (df["კატეგორია"].isin(selected_cat))
        if search_query:
            mask = mask & (df["დასახელება"].str.contains(search_query, case=False, na=False))

        filtered_df = df[mask]

        # სტატისტიკა
        c1, c2, c3 = st.columns(3)
        c1.metric("სულ დასახელება", len(filtered_df))
        c2.metric("საშუალო ფასი", f"{round(filtered_df['ფასი (₾)'].mean(), 2) if not filtered_df.empty else 0} ₾")
        c3.metric("მარაგი ჯამში", int(filtered_df["რაოდენობა"].sum()))

        st.dataframe(filtered_df.sort_values(by="ფასი (₾)", ascending=True), width="stretch", hide_index=True)

        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 ჩამოტვირთე CSV", csv, 'inventory.csv', 'text/csv')
    else:
        st.warning("მონაცემები ცარიელია.")