import streamlit as st
from apify_client import ApifyClient
import google.generativeai as genai
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="AdSpy & Creative Generator", page_icon="🚀", layout="wide")

st.title("🚀 AdSpy & Creative Generator (MVP)")
st.caption("Trouvez les pubs gagnantes et générez des concepts créatifs basés sur des données réelles.")

# Récupération sécurisée des clés API depuis Streamlit Secrets
APIFY_TOKEN = st.secrets.get("APIFY_TOKEN")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

if not APIFY_TOKEN or not GEMINI_API_KEY:
    st.error("⚠️ Les clés API ne sont pas configurées dans les Secrets Streamlit.")
    st.stop()

apify_client = ApifyClient(APIFY_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# Formulaire utilisateur
with st.form("search_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("Secteur, produit ou mot-clé :", "Montre connectée")
    with col2:
        min_days = st.number_input("Ancienneté min. (jours) :", min_value=7, value=30, step=7)
    
    submitted = st.form_submit_button("🔍 Lancer la recherche & l'analyse")

if submitted:
    st.info(f"Recherche des publicités pour **'{keyword}'** actives depuis au moins {min_days} jours...")
    
    try:
        
search_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={keyword}"
run_input = {
    "urls": [{"url": search_url}],
    "count": 10
}
        
        with st.spinner("Extraction des publicités en cours..."):
            run = apify_client.actor("curious_coder/facebook-ads-library-scraper").call(run_input=run_input)
            raw_items = apify_client.dataset(run["defaultDatasetId"]).list_items().items

        # Filtrage par durée
        filtered_items = []
        now = datetime.now()
        
        for item in raw_items:
            start_date_str = item.get("startDate") or item.get("adStartDate")
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
                    days_active = (now - start_date).days
                    if days_active >= min_days:
                        item["calculated_days"] = days_active
                        filtered_items.append(item)
                except ValueError:
                    filtered_items.append(item)

        if not filtered_items:
            st.warning(f"Aucune publicité active depuis plus de {min_days} jours n'a été trouvée pour ce mot-clé.")
        else:
            st.success(f"🎉 {len(filtered_items)} publicités gagnantes identifiées !")
            st.divider()

            model = genai.GenerativeModel('gemini-1.5-flash')

            for idx, item in enumerate(filtered_items[:5], 1):
                page_name = item.get("pageName", "Annonceur inconnu")
                ad_text = item.get("adText", "Pas de texte extrait")
                days_active = item.get("calculated_days", "30+")

                st.markdown(f"### Pub #{idx} : **{page_name}** *(Active depuis ~{days_active} jours)*")

                col_data, col_ai = st.columns([1, 1])

                with col_data:
                    st.markdown("**📝 Copy/Texte original :**")
                    st.info(ad_text)

                with col_ai:
                    with st.spinner("Analyse IA et génération d'idées..."):
                        prompt = f"""
                        Tu es un expert en Marketing Direct et créations publicitaires.
                        Voici le texte d'une publicité Meta qui tourne depuis plus de {days_active} jours :
                        
                        ---
                        {ad_text}
                        ---
                        
                        Analyse cette publicité en français :
                        1. **Accroche (Hook) :** Quelle est la formule/technique utilisée ?
                        2. **Angle psychologique :** Quel problème ou désir est ciblé ?
                        3. **Concept dérivé :** Propose une idée de nouvelle publicité (script court ou copy) basée sur cette structure.
                        """
                        response = model.generate_content(prompt)
                        st.markdown(response.text)

                st.divider()

    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")
