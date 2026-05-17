import streamlit as st
import pandas as pd
import os
import streamlit_authenticator as stauth
from database.database_manager import DatabaseManager
from dotenv import load_dotenv
from utils.data_loader import sync_inventory, load_inventory_df

# 1. საწყისი კონფიგურაცია
load_dotenv()
st.set_page_config(page_title="Inventory Manager", layout="wide", page_icon="🖥️")
db = DatabaseManager()
db.create_user_table()  # ქმნის ცხრილს, თუ არ არსებობს

# 🚀 რეჟიმის ინიციალიზაცია (ავტორიზაციისა და რეგისტრაციის გვერდების გამიჯვნა)
if 'auth_mode' not in st.session_state:
    st.session_state['auth_mode'] = 'login'


# 2. მომხმარებლების ჩატვირთვა ბაზის მენეჯერიდან (SQL ლოგიკის გარეშე UI-ში)
def load_users_from_db():
    return db.get_all_users()


# 3. ავტორიზაციის მომზადება
if 'credentials' not in st.session_state or st.session_state.get('reload_users'):
    st.session_state['credentials'] = load_users_from_db()
    st.session_state['reload_users'] = False

# გასაღები უსაფრთხოდ იკითხება .env ფაილიდან
cookie_signature_key = os.getenv('AUTH_COOKIE_KEY', 'fallback_secret_key_for_safety')

authenticator = stauth.Authenticate(
    st.session_state['credentials'],
    'inventory_cookie',
    cookie_signature_key,
    cookie_expiry_days=30
)

# --- CSS სტილი (Dark Mode ბლოკები შენარჩუნებულია) ---
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

authentication_status = st.session_state.get('authentication_status')

# =================================================================
# 4. მთავარი კონტენტი (მხოლოდ ავტორიზებული მომხმარებლებისთვის)
# =================================================================
if authentication_status:
    with st.sidebar:
        st.write(f"👋 მომხმარებელი: **{st.session_state['name']}**")
        authenticator.logout(location='sidebar')
        st.divider()
        st.header("🔍 ფილტრაცია")

    st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი")

    # საწყისი ავტომატური სინქრონიზაცია (გაეშვება მხოლოდ პირველ ჩართვაზე)
    if 'initial_sync_done' not in st.session_state:
        # noinspection PyTypeChecker
        with st.spinner("მიმდინარეობს საწყისი სინქრონიზაცია..."):
            sync_inventory()
        st.session_state['initial_sync_done'] = True

    # --- Sidebar: ბაზის იძულებითი განახლების ღილაკი ---
    st.sidebar.header("🔄 მონაცემთა ბაზა")
    if st.sidebar.button("მონაცემების სინქრონიზაცია"):
        # noinspection PyTypeChecker
        with st.spinner("მიმდინარეობს ბაზის განახლება..."):
            sync_inventory()
            st.cache_data.clear()
        st.success("ბაზა წარმატებით განახლდა!")
        st.rerun()

    # მონაცემების უსაფრთხო ჩატვირთვა ქეშირებული საერთო მოდულიდან (Read-Only)
    df = load_inventory_df()

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
        c3.metric("მარაგი ჯამში", int(filtered_df["რაოდენობა"].sum()) if not filtered_df.empty else 0)

        # მონაცემთა ცხრილი (სორტირებითა და დამალული ინდექსით)
        st.dataframe(filtered_df.sort_values(by="ფასი (₾)", ascending=True), use_container_width=True, hide_index=True)

        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 ჩამოტვირთე CSV", csv, 'inventory.csv', 'text/csv')
    else:
        st.warning("მონაცემები ცარიელია. დააჭირეთ 'მონაცემების სინქრონიზაცია'-ს.")


# =================================================================
# 5. ავტორიზაციისა და რეგისტრაციის ბლოკი (ცალკეული ეკრანების ნაკადი)
# =================================================================
else:
    # ---------------- ეკრანი 1: ავტორიზაცია ----------------
    if st.session_state['auth_mode'] == 'login':
        authenticator.login(location='main')
        if st.session_state.get('authentication_status') == False:
            st.error('მომხმარებლის სახელი ან პაროლი არასწორია')
        elif st.session_state.get('authentication_status') is None:
            st.info('გთხოვთ შეიყვანოთ მონაცემები სისტემაში შესასვლელად')

        st.write("")
        st.write("ჯერ არ გაქვთ სისტემის ანგარიში?")
        if st.button("📝 ახალი მომხმარებლის რეგისტრაცია"):
            st.session_state['auth_mode'] = 'register'
            st.rerun()

    # ---------------- ეკრანი 2: რეგისტრაცია ----------------
    elif st.session_state['auth_mode'] == 'register':
        st.title("📝 ახალი მომხმარებლის რეგისტრაცია")
        try:
            if authenticator.register_user(location='main'):
                # სტაბილური ვალიდაცია ბაზის იუზერნეიმების შედარებით
                db_usernames = db.get_all_usernames()
                current_users = st.session_state['credentials'].get('usernames', {})

                for u_name, u_data in current_users.items():
                    if u_name not in db_usernames:
                        u_email = u_data.get('email', '')
                        u_name_real = u_data.get('name', u_name)
                        u_pass = u_data.get('password', '')

                        # უსაფრთხო შენახვა ბაზაში სწორი პარამეტრების მიმდევრობით
                        db.add_user(u_name, u_pass, u_email, u_name_real)
                        st.success('რეგისტრაცია წარმატებულია! გადადით ავტორიზაციის გვერდზე.')
                        st.session_state['reload_users'] = True
                        st.session_state['auth_mode'] = 'login'
                        st.rerun()
        except Exception as e:
            st.error(f"რეგისტრაციის შეცდომა: {e}")

        st.write("")
        if st.button("🔙 უკვე გაქვთ ანგარიში? ავტორიზაციის გვერდი"):
            st.session_state['auth_mode'] = 'login'
            st.rerun()