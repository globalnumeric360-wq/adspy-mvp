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
        keyword = st.text_input("Secteur, produit ou mot-clé :", "bain de bouche")
    with col2:
        min_days = st.number_input("Ancienneté min. (jours) :", min_value=0, value=7, step=7)
    
    submitted = st.form_submit_button("🔍 Lancer la recherche & l'analyse")

if submitted:
    st.info(f"Recherche des publicités pour **'{keyword}'**...")
    
    try:
        # Format d'entrée pour le scraper Apify Facebook Ads
        search_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={keyword}"
        run_input = {
            "urls": [{"url": search_url}],
            "count": 15
        }
        
        with st.spinner("Extraction des publicités en cours..."):
            run = apify_client.actor("curious_coder/facebook-ads-library-scraper").call(run_input=run_input)
            
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
            raw_items = apify_client.dataset(dataset_id).list_items().items

        # Filtrage souple
        filtered_items = []
        now = datetime.now()
        
        for item in raw_items:
            start_date_str = item.get("startDate") or item.get("adStartDate") or item.get("publisherPlatform")
            days_active = "N/A"
            
            if start_date_str and isinstance(start_date_str, str) and len(start_date_str) >= 10:
                try:
                    start_date = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
                    days_calculated = (now - start_date).days
                    if days_calculated >= min_days:
                        days_active = days_calculated
                        item["calculated_days"] = days_active
                        filtered_items.append(item)
                except ValueError:
                    filtered_items.append(item)
            else:
                # Si pas de date précise, on conserve la pub
                filtered_items.append(item)

        if not raw_items:
            st.warning(f"Aucune publicité trouvée pour le terme '{keyword}'.")
        else:
            items_to_display = filtered_items if filtered_items else raw_items
            st.success(f"🎉 {len(items_to_display)} publicités identifiées !")
            st.divider()

            model = genai.GenerativeModel('gemini-2.5-flash')

            for idx, item in enumerate(items_to_display[:5], 1):
                page_name = item.get("pageName") or item.get("page_name") or "Annonceur"
                ad_text = item.get("adText") or item.get("ad_creative_bodies") or item.get("snapshot", {}).get("body", {}).get("markup") or "Publicité visuelle sans texte long."
                
                # Nettoyage succinct si c'est une liste
                if isinstance(ad_text, list):
                    ad_text = " ".join(ad_text)

                days_active = item.get("calculated_days", "Récente")

                st.markdown(f"### Pub #{idx} : **{page_name}** *(Statut : Active)*")

                col_data, col_ai = st.columns([1, 1])

                with col_data:
                    st.markdown("**📝 Copy/Texte de la publicité :**")
                    st.info(ad_text)

                with col_ai:
                    with st.spinner("Analyse IA et génération d'idées..."):
                        prompt = f"""
                        Tu es un expert mondial en Marketing Direct et création publicitaire.
                        Voici le texte d'une publicité Meta active :
                        
                        ---
                        {ad_text}
                        ---
                        
                        Réalise l'analyse suivante en français clair :
                        1. **Accroche (Hook) :** Quelle est la technique utilisée pour capter l'attention ?
                        2. **Angle psychologique :** Quel problème ou désir est ciblé ?
                        3. **Concept dérivé :** Propose une idée de nouvelle publicité (script court ou copy) basée sur cette structure.
                        """
                        response = model.generate_content(prompt)
                        st.markdown(response.text)

                st.divider()

    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")
