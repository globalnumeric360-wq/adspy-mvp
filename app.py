import streamlit as st
from apify_client import ApifyClient
import google.generativeai as genai
import urllib.parse # Pour gérer les espaces dans les liens

# Configuration de la page
st.set_page_config(page_title="AdSpy & Creative Generator", page_icon="🚀", layout="wide")

st.title("🚀 AdSpy & Creative Generator (MVP)")
st.caption("Trouvez les pubs gagnantes et générez des concepts créatifs basés sur des données réelles.")

# Récupération sécurisée des clés API
APIFY_TOKEN = st.secrets.get("APIFY_TOKEN")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

if not APIFY_TOKEN:
    st.error("⚠️ Le token APIFY_TOKEN n'est pas configuré.")
    st.stop()

apify_client = ApifyClient(APIFY_TOKEN)

# Mémoire (Session State) pour éviter la réinitialisation
if "ads_data" not in st.session_state:
    st.session_state.ads_data = None
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""

# Formulaire utilisateur
with st.form("search_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("Secteur, produit ou mot-clé :", "bain de bouche")
    with col2:
        min_days = st.number_input("Ancienneté min. (jours) :", min_value=0, value=7, step=7)
    
    submitted = st.form_submit_button("🔍 Lancer la recherche")

if submitted:
    st.session_state.search_keyword = keyword
    st.info(f"Recherche des publicités pour **'{keyword}'**...")
    
    try:
        # Encodage propre du mot-clé (ex: "bain de bouche" devient "bain%20de%20bouche")
        safe_keyword = urllib.parse.quote(keyword)
        search_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={safe_keyword}"
        
        run_input = {
            "urls": [{"url": search_url}],
            "count": 15
        }
        
        with st.spinner("Extraction des publicités en cours..."):
            run = apify_client.actor("curious_coder/facebook-ads-library-scraper").call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
            raw_items = apify_client.dataset(dataset_id).list_items().items

        if not raw_items:
            st.warning(f"Aucune publicité trouvée pour le terme '{keyword}'.")
            st.session_state.ads_data = None
        else:
            st.session_state.ads_data = raw_items

    except Exception as e:
        st.error(f"Erreur d'extraction : {e}")

# Affichage des publicités et Analyse IA
if st.session_state.ads_data:
    st.success(f"🎉 {len(st.session_state.ads_data)} publicités identifiées !")
    st.divider()

    for idx, item in enumerate(st.session_state.ads_data[:5], 1):
        page_name = item.get("pageName") or item.get("page_name") or "Annonceur"
        
        ad_text = item.get("adText") or item.get("ad_creative_bodies") or "Publicité visuelle sans texte."
        if isinstance(ad_text, list):
            ad_text = " ".join(ad_text)
            
        # Correction 1 : Liens robustes et cliquables
        ad_id = item.get("id") or item.get("adArchiveID")
        safe_keyword2 = urllib.parse.quote(st.session_state.search_keyword)
        
        if ad_id:
            ad_url = f"https://www.facebook.com/ads/library/?id={ad_id}"
        else:
            ad_url = item.get("snapshotUrl") or f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={safe_keyword2}"

        st.markdown(f"### Pub #{idx} : **{page_name}**")
        
        col_data, col_ai = st.columns([1, 1])

        with col_data:
            st.markdown("**📝 Texte de la publicité :**")
            st.info(ad_text)
            # Lien encodé, garanti de ne pas se casser
            st.markdown(f"👉 [**Consulter la pub sur Meta**]({ad_url})")

        with col_ai:
            st.markdown("**💡 Analyse & Idées Créatives :**")
            if st.button(f"✨ Analyser la pub #{idx}", key=f"btn_{idx}"):
                if not GEMINI_API_KEY:
                    st.warning("⚠️ Clé GEMINI_API_KEY absente.")
                else:
                    with st.spinner("Génération par l'IA en cours..."):
                        genai.configure(api_key=GEMINI_API_KEY)
                        prompt = f"""
                        Tu es un expert en Growth Marketing. Analyse cette publicité Meta :
                        ---
                        {ad_text}
                        ---
                        Réponds en français :
                        1. **Accroche (Hook) :** Quelle est la technique utilisée ?
                        2. **Angle psychologique :** Quel désir/problème est visé ?
                        3. **Concept dérivé :** Propose une idée de nouvelle publicité inspirée de cette structure.
                        """
                        
                        # Correction 2 : Fallback automatique du modèle
                        try:
                            # Tentative avec le modèle récent
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            res = model.generate_content(prompt)
                            st.markdown(res.text)
                        except Exception:
                            try:
                                # Plan B : le modèle universel garanti
                                model_fallback = genai.GenerativeModel('gemini-pro')
                                res_fallback = model_fallback.generate_content(prompt)
                                st.markdown(res_fallback.text)
                            except Exception as e_final:
                                st.error(f"L'API Gemini rencontre une erreur : {e_final}")

        st.divider()
