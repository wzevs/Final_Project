import io
import os
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
from database.database_manager import DatabaseManager
from dotenv import load_dotenv
from services.storera_service import StoreraService
from utils.data_loader import load_inventory_df, sync_inventory


# =================================================================
# 🚀 ექსელის დამუშავებისა და რეპორტინგის ერთიანი ფუნქცია
# =================================================================
def render_storera_ui(db_manager: DatabaseManager):
    """Storera-ს ექსელის ფაილის ოპტიმიზაციისა და ცვლილებების ჩვენების ბლოკი"""
    st.divider()
    st.subheader("🔄 Storera-ს მარაგების ჭკვიანი სინქრონიზაცია")
    st.write(
        "ატვირთეთ Storera-დან ექსპორტირებული პროდუქციის ექსელის ფაილი (`.xlsx`). "
        "სისტემა ავტომატურად განაახლებს მხოლოდ მარაგებს, თქვენს ხელით დაყენებულ ფასებს კი ხელუხლებლად დატოვებს."
    )

    storera_file = st.file_uploader(
        "აირჩიეთ Storera-ს პროდუქტების ექსელის ფაილი (.xlsx)",
        type=["xlsx"],
        key="storera_global_excel_upload"
    )

    if storera_file is not None:
        try:
            storera_input_df = pd.read_excel(storera_file)

            if st.button("🚀 მარაგების ოპტიმიზაცია", key="storera_global_opt_btn"):
                storera_service = StoreraService(db_manager)

                with st.spinner("მიმდინარეობს მოდელების ძებნა და მარაგების გაანგარიშება..."):
                    final_df, changes_df = storera_service.process_storera_feed(storera_input_df)

                st.success("ოპტიმიზაცია წარმატებით დასრულდა!")

                # 📊 ცვლილებების ვიზუალური რეპორტი სტრიმლიტში
                if not changes_df.empty:
                    st.subheader("📊 მარაგების ცვლილების რეპორტი")

                    total_changes = len(changes_df)
                    zeroed_out = len(changes_df[changes_df["სტატუსი"] == "❌ ამოიწურა"])
                    updated_stocks = len(changes_df[changes_df["სტატუსი"] == "🔄 განახლდა"])

                    col_log1, col_log2, col_log3 = st.columns(3)
                    col_log1.metric("სულ შეიცვალა", f"{total_changes} ნივთი")
                    col_log2.metric("მარაგი განახლდა", f"{updated_stocks} ცალი")
                    col_log3.metric("საიტზე გათიშა (0)", f"{zeroed_out} ნივთი")

                    st.write("ცვლილებების დეტალური ჩამონათვალი:")
                    st.dataframe(changes_df, width='stretch', hide_index=True)
                else:
                    st.info(
                        "ყველა პროდუქტის მარაგი უკვე იდეალურ თანხვედრაშია მომწოდებლებთან და ცვლილება არ დასჭირვებია.")

                # 📥 ფაილის გენერაცია ჩამოტვირთვისთვის
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='პროდუქციის ჩამონათვალი')
                buffer.seek(0)

                st.download_button(
                    label="📥 ჩამოტვირთე განახლებული Storera Excel (.xlsx)",
                    data=buffer,
                    file_name="storera_optimized_products.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="storera_global_download_btn"
                )
        except Exception as e:
            st.error(f"ფაილის დამუშავებისას მოხდა შეცდომა: {e}")


# =================================================================
# 🔒 ეს კოდი გაეშვება მხოლოდ მაშინ, როცა პირდაპირ ვრთავთ app.py-ს
# =================================================================
if __name__ == "__main__":
    load_dotenv()
    st.set_page_config(page_title="Inventory Manager", layout="wide", page_icon="🖥️")
    db = DatabaseManager()
    db.create_user_table()

    if 'auth_mode' not in st.session_state:
        st.session_state['auth_mode'] = 'login'


    def load_users_from_db():
        return db.get_all_users()


    if 'credentials' not in st.session_state or st.session_state.get('reload_users'):
        st.session_state['credentials'] = load_users_from_db()
        st.session_state['reload_users'] = False

    cookie_signature_key = os.getenv('AUTH_COOKIE_KEY', 'fallback_secret_key_for_safety')

    authenticator = stauth.Authenticate(
        st.session_state['credentials'],
        'inventory_cookie',
        cookie_signature_key,
        cookie_expiry_days=30
    )

    # --- CSS სტილიზაცია ---
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

    if authentication_status:
        with st.sidebar:
            st.write(f"👋 მომხმარებელი: **{st.session_state['name']}**")
            authenticator.logout(location='sidebar')
            st.divider()
            st.header("🔍 ფილტრაცია")

        st.title("🖥️ კომპიუტერული ნაწილების ინვენტარი")

        if 'initial_sync_done' not in st.session_state:
            with st.spinner("მიმდინარეობს საწყისი სინქრონიზაცია..."):
                sync_inventory()
            st.session_state['initial_sync_done'] = True

        st.sidebar.header("🔄 მონაცემთა ბაზა")
        if st.sidebar.button("მონაცემების სინქრონიზაცია"):
            with st.spinner("მიმდინარეობს ბაზის განახლება..."):
                sync_inventory()
                st.cache_data.clear()
            st.success("ბაზა წარმატებით განახლდა!")
            st.rerun()

        df = load_inventory_df()

        if not df.empty:
            selected_brand = st.sidebar.multiselect("Mომწოდებელი:", options=df["მომწოდებელი"].unique(),
                                                    default=df["მომწოდებელი"].unique())
            selected_cat = st.sidebar.multiselect("კატეგორია:", options=df["კატეგორია"].unique(),
                                                  default=df["კატეგორია"].unique())
            search_query = st.text_input("მოძებნე პროდუქტი:", "")

            mask = (df["მომწოდებელი"].isin(selected_brand)) & (df["კატეგორია"].isin(selected_cat))
            if search_query:
                mask = mask & (df["დასახელება"].str.contains(search_query, case=False, na=False))

            filtered_df = df[mask]

            c1, c2, c3 = st.columns(3)
            c1.metric("სულ დასახელება", len(filtered_df))
            c2.metric("საშუალო ფასი", f"{round(filtered_df['ფასი (₾)'].mean(), 2) if not filtered_df.empty else 0} ₾")
            c3.metric("მარაგი ჯამში", int(filtered_df["რაოდენობა"].sum()) if not filtered_df.empty else 0)

            # განახლებული width='stretch'
            st.dataframe(filtered_df.sort_values(by="ფასი (₾)", ascending=True), width='stretch', hide_index=True)

            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 ჩამოტვირთე სრული სია (CSV)", csv, 'inventory.csv', 'text/csv')
        else:
            st.warning("მონაცემები ცარიელია. დააჭირეთ 'მონაცემების სინქრონიზაცია'-ს.")

        # 🚀 ვიძახებთ ექსელის დამუშავების ფუნქციას
        render_storera_ui(db)

    else:
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

        elif st.session_state['auth_mode'] == 'register':
            st.title("📝 ახალი მომხმარებლის რეგისტრაცია")
            try:
                if authenticator.register_user(location='main'):
                    db_usernames = db.get_all_usernames()
                    current_users = st.session_state['credentials'].get('usernames', {})

                    for u_name, u_data in current_users.items():
                        if u_name not in db_usernames:
                            u_email = u_data.get('email', '')
                            u_name_real = u_data.get('name', u_name)
                            u_pass = u_data.get('password', '')

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