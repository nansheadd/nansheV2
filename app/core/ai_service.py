# Fichier: nanshe/backend/app/core/ai_service.py (VERSION REFACTORISÉE)

import json
import logging
import requests
import tiktoken
from sqlalchemy.orm import Session
from app.models.user.user_model import User

from app.models.analytics.golden_examples_model import GoldenExample
from app.models.analytics.ai_token_log_model import AITokenLog

from openai import OpenAI



from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core import prompt_manager
from app.utils.json_utils import safe_json_loads  # <-- util JSON robuste
from app.core.embeddings import get_text_embedding as _compute_text_embedding

logger = logging.getLogger(__name__)

MODEL_PRICING = {
    "gpt-5-mini-2025-08-07": {"input": 0.15, "output": 0.60},
    # Ajoutez les autres modèles ici
}

class _SimpleEncoding:
    """Fallback tokenizer that approximates token counting offline."""

    @staticmethod
    def encode(text: str) -> list[int]:
        tokens = (text or "").split()
        return list(range(len(tokens)))


def _load_tiktoken_encoding() -> "tiktoken.Encoding | _SimpleEncoding":
    try:
        return tiktoken.encoding_for_model("gpt-5-mini-2025-08-07")
    except Exception as exc:  # pragma: no cover - depends on network
        logger.warning("Tiktoken model unavailable (%s), fallback to cl100k_base.", exc)
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception as fallback_exc:  # pragma: no cover - offline fallback
            logger.warning(
                "Tiktoken encodings indisponibles (%s). Utilisation d'un tokenizeur simple.",
                fallback_exc,
            )
            return _SimpleEncoding()


encoding = _load_tiktoken_encoding()

def _call_ai_with_rag_examples(db: Session, user: User, user_prompt: str, system_prompt_template: str, feature_name: str, example_type: str, model_choice: str, prompt_variables: dict) -> Dict[str, Any]:
    prompt_embedding = get_text_embedding(user_prompt)
    similar_examples = db.query(GoldenExample.content).filter(GoldenExample.example_type == example_type).order_by(GoldenExample.embedding.l2_distance(prompt_embedding)).limit(3).all()
    rag_examples = "\n\n".join([ex[0] for ex in similar_examples])
    final_system_prompt = prompt_manager.get_prompt(system_prompt_template, rag_examples=rag_examples, ensure_json=True, **prompt_variables)
    return call_ai_and_log(db=db, user=user, model_choice=model_choice, system_prompt=final_system_prompt, user_prompt=user_prompt, feature_name=feature_name)

def get_text_embedding(text: str, *, allow_remote: bool | None = None) -> list[float]:
    """Wrapper conservé pour compatibilité avec l'ancien import."""

    return _compute_text_embedding(text, allow_remote=allow_remote)


def _truncate_for_prompt(text: str, max_chars: int = 20000) -> str:
    if not text or not isinstance(text, str):
        return ""
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars]


def _looks_like_heading(line: str) -> bool:
    if not line:
        return False
    if len(line) <= 4:
        return False
    upper_ratio = sum(1 for ch in line if ch.isupper()) / max(len(line), 1)
    digit_ratio = sum(1 for ch in line if ch.isdigit()) / max(len(line), 1)
    has_colon = ':' in line
    starts_with_numbering = bool(
        line[:8].strip().startswith(tuple(f"{i}." for i in range(1, 10)))
    ) or line[:8].strip().startswith(tuple(f"{i})" for i in range(1, 10)))
    is_uppercase_heading = upper_ratio > 0.6 and line == line.upper()
    return is_uppercase_heading or starts_with_numbering or has_colon or digit_ratio > 0.2


def _segment_document(text: str) -> tuple[list[str], list[str]]:
    lines = [line.strip() for line in text.splitlines()] if text else []
    cleaned_lines = [line for line in lines if line]

    outline: list[str] = []
    for line in cleaned_lines:
        if len(outline) >= 20:
            break
        if _looks_like_heading(line):
            outline.append(line)

    if not outline:
        outline = cleaned_lines[:12]

    paragraphs: list[str] = []
    buffer: list[str] = []
    for raw_line in lines:
        if not raw_line.strip():
            if buffer:
                paragraph = " ".join(buffer).strip()
                if len(paragraph) > 40:
                    paragraphs.append(paragraph)
                buffer = []
        else:
            buffer.append(raw_line.strip())
    if buffer:
        paragraph = " ".join(buffer).strip()
        if len(paragraph) > 40:
            paragraphs.append(paragraph)

    dense_paragraphs = [p for p in paragraphs if len(p.split()) > 8]
    highlights = dense_paragraphs[:12] if dense_paragraphs else paragraphs[:12]

    return outline, highlights

def call_ai_and_log(db: Session, user: User, model_choice: str, system_prompt: str, user_prompt: str, feature_name: str) -> Dict[str, Any]:
    prompt_tokens = len(encoding.encode(system_prompt + user_prompt))
    response_data = _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)
    response_text = json.dumps(response_data)
    completion_tokens = len(encoding.encode(response_text))
    cost = 0.0
    if model_choice in MODEL_PRICING:
        prices = MODEL_PRICING[model_choice]
        cost = ((prompt_tokens / 1_000_000) * prices["input"]) + ((completion_tokens / 1_000_000) * prices["output"])
    log_entry = AITokenLog(user_id=user.id, feature=feature_name, model_name=model_choice, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost)
    db.add(log_entry)
    db.commit()
    return response_data

def _summarize_text_for_prompt(db: Session, user: User, text_to_summarize: str, prompt_name: str) -> str:
    system_prompt = prompt_manager.get_prompt(prompt_name, text_to_summarize=text_to_summarize, ensure_json=True)
    try:
        response_data = call_ai_and_log(db=db, user=user, model_choice="openai_gpt4o-mini", system_prompt=system_prompt, user_prompt="Effectue la tâche de résumé demandée.", feature_name=f"summarizer_{prompt_name}")
        return response_data.get("summary", text_to_summarize)
    except Exception as e:
        logger.error(f"Échec de la summarisation avec le prompt {prompt_name}: {e}")

_GEMINI_MODEL = "gemini-1.5-pro-latest"
_GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent"
)

if settings.GOOGLE_API_KEY:
    logger.info("✅ Service IA Gemini configuré pour l'appel REST.")
else:
    logger.warning("⚠️ Clé API Google Gemini absente. Les appels Gemini échoueront.")

try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("✅ Client OpenAI configuré.")
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur de configuration pour OpenAI: {e}")

def _call_gemini(prompt: str, temperature: Optional[float] = None) -> str:
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        raise ConnectionError("Le modèle Gemini n'est pas disponible (clé API manquante).")

    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    if temperature is not None:
        payload["generationConfig"]["temperature"] = temperature

    try:
        response = requests.post(
            _GEMINI_ENDPOINT,
            params={"key": api_key},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Erreur lors de l'appel à l'API Gemini : %s", exc)
        raise

    data: dict[str, Any] = response.json()
    try:
        candidates = data.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
            combined = "".join(texts).strip()
            if combined:
                return combined
    except Exception as exc:  # pragma: no cover - parsing defensive
        logger.error("Réponse Gemini inattendue: %s", exc, exc_info=True)
        raise ValueError("Réponse Gemini invalide") from exc

    logger.error("Réponse Gemini sans contenu exploitable: %s", data)
    raise ValueError("Réponse Gemini vide")

def _inject_json_guard(system_prompt: str, user_prompt: str) -> str:
    sp = (system_prompt or "").strip()
    combined = (sp + " " + (user_prompt or "")).lower()
    if "json" not in combined:
        sp = (sp + "\n\nRéponds en json strict (json uniquement).").strip()
    return sp

def _call_openai_llm(user_prompt: str, system_prompt: str = "", temperature: Optional[float] = None) -> str:
    if not openai_client: raise ConnectionError("Le client OpenAI n'est pas configuré.")
    sp = _inject_json_guard(system_prompt, user_prompt)
    messages = [{"role": "system", "content": sp}, {"role": "user", "content": user_prompt}]
    try:
        logger.info("Appel à l'API OpenAI avec le modèle gpt-5-mini-2025-08-07")
        response = openai_client.chat.completions.create(model="gpt-5-mini-2025-08-07", messages=messages, response_format={"type": "json_object"})
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Une erreur API est survenue avec OpenAI : {e}")
        raise

def _call_local_llm(user_prompt: str, system_prompt: str = "", temperature: Optional[float] = None) -> str:
    if not settings.LOCAL_LLM_URL: raise ConnectionError("L'URL du LLM local (Ollama) n'est pas configurée.")
    full_url = f"{settings.LOCAL_LLM_URL.rstrip('/')}/api/chat"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    payload: Dict[str, Any] = {"model": "llama3:8b", "messages": messages, "format": "json", "stream": False}
    if temperature is not None: payload["options"] = {"temperature": temperature}
    try:
        response = requests.post(full_url, json=payload, timeout=120)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        if content and content.strip() not in ["{}", "[]"]: return content
        raise ValueError("Ollama a renvoyé une réponse vide ou malformée.")
    except requests.exceptions.RequestException as e:
        logger.error(f"ERREUR CRITIQUE lors de l'appel à Ollama : {e}")
        raise

def _call_ai_model(user_prompt: str, model_choice: str, system_prompt: str = "") -> str:
    logger.info(f"Appel à l'IA avec le modèle : {model_choice}")
    if model_choice == "local": return _call_local_llm(user_prompt=user_prompt, system_prompt=system_prompt)
    elif model_choice.startswith("openai_"): return _call_openai_llm(user_prompt=user_prompt, system_prompt=system_prompt)
    else:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        return _call_gemini(full_prompt)

def _call_ai_model_json(user_prompt: str, model_choice: str, system_prompt: str = "", max_retries: int = 2) -> Dict[str, Any]:
    last_exc: Optional[Exception] = None
    sys_base = system_prompt or ""
    repair = "\n\n[CONTRAINTE DE SORTIE]\n- Ta réponse précédente n'était pas un JSON valide.\n- Réponds STRICTEMENT avec un unique objet JSON valide.\n- Pas de backticks, pas de commentaires, pas de texte hors JSON."
    for attempt in range(max_retries + 1):
        use_openai = model_choice.startswith("openai_")
        temp = None if use_openai else (0.2 if attempt == 0 else 0.0)
        sys_used = sys_base if attempt == 0 else (sys_base + repair)
        try:
            if model_choice == "local": 
                raw = _call_local_llm(user_prompt=user_prompt, system_prompt=sys_used, temperature=temp or 0.0)
            
            # --- CORRECTION : On force l'utilisation d'OpenAI ---
            # Si le modèle commence par "openai_" OU si c'est le cas par défaut, on utilise OpenAI.
            else: 
                raw = _call_openai_llm(user_prompt=user_prompt, system_prompt=sys_used, temperature=temp)
            
            # La partie qui appelait Gemini est maintenant ignorée.

            data = safe_json_loads(raw)
            if isinstance(data, list): data = {"exercises": data}
            return data
        except Exception as e:
            last_exc = e
            logger.warning(f"Tentative JSON {attempt+1}/{max_retries+1} échouée: {e}")
    raise last_exc if last_exc else RuntimeError("Échec d'appel JSON sans exception d'origine.")



def classify_course_topic(title: str, model_choice: str) -> str:
    system_prompt = prompt_manager.get_prompt("course_planning.classify_topic", ensure_json=True)
    try:
        data = _call_ai_model_json(title, model_choice, system_prompt=system_prompt)
        return data.get("category", "general")
    except Exception as e:
        logger.error(f"Erreur de classification pour '{title}': {e}")
        return "general"

def generate_learning_plan(title: str, course_type: str, model_choice: str) -> dict:
    system_prompt = prompt_manager.get_prompt("course_planning.generic_plan", ensure_json=True)
    user_prompt = f"Sujet du cours : {title}. Catégorie : {course_type}."
    try: return _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur de plan de cours pour '{title}': {e}")
        return {}


def generate_learning_plan_from_document(
    document_text: str,
    title: str,
    domain: str,
    area: str,
    main_skill: str,
    model_choice: str,
) -> dict | None:
    excerpt = _truncate_for_prompt(document_text, max_chars=12000)
    if not excerpt:
        return None

    logger.info("IA Service: génération d'un plan contextualisé à partir d'un document pour '%s'", title)
    outline, highlights = _segment_document(excerpt)
    outline_block = "\n".join(f"- {item}" for item in outline) if outline else "- Aucun heading extrait"
    highlight_block = "\n\n".join(
        f"[Extrait {idx+1}] {p[:320]}" for idx, p in enumerate(highlights)
    ) if highlights else "Aucun extrait riche identifié"

    system_prompt = f"""
Tu es un expert en ingénierie pédagogique. À partir du document fourni, construis un plan d'apprentissage gamifié.

[MÉTADONNÉES DU DOCUMENT]
- Titre cible : {title}
- Domaine : {domain}
- Aire : {area}
- Compétence principale : {main_skill}

[STRUCTURE DÉTECTÉE]
{outline_block}

[EXTRAITS CLÉS]
{highlight_block}

[CONTRAINTES DE SORTIE]
- Retourne un objet JSON unique avec la structure suivante :
  {{
    "overview": {{
        "title": "{title}",
        "domain": "{domain}",
        "area": "{area}",
        "main_skill": "{main_skill}",
        "target_audience": "",
        "source": {{"type": "pdf", "description": "plan généré depuis un document"}}
    }},
    "levels": [
        {{
            "level_title": "",
            "xp_target": 0,
            "summary": "",
            "chapters": [
                {{
                    "chapter_title": "",
                    "chapter_summary": "",
                    "learning_objectives": [""],
                    "key_points": [""],
                    "source_excerpt": [""],
                    "assessment_hint": ""
                }}
            ]
        }}
    ]
  }}
- Le plan doit contenir entre 8 et 20 levels maximum.
- Chaque chapter doit référencer explicitement le document :
  * "chapter_summary" et "learning_objectives" reprennent des idées du document.
  * "source_excerpt" contient 1 à 3 citations directes (≤ 240 caractères chacune) extraites mot pour mot du PDF.
- N'invente aucune notion absente du document. Si une section manque d'information, indique-le clairement.
- Évite les généralités : reste ancré dans le vocabulaire du PDF.
"""

    user_prompt = (
        "[DOCUMENT À SYNTHÉTISER — EXTRAIT LIMITÉ]\n"
        f"{excerpt}\n"
        "[FIN DU DOCUMENT]\n"
        "Respecte strictement les contraintes ci-dessus pour construire le plan JSON."
    )

    try:
        return _call_ai_model_json(
            user_prompt=user_prompt,
            model_choice=model_choice,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error("Erreur lors de la génération du plan contextualisé: %s", exc, exc_info=True)
        return None


def generate_programming_learning_plan(topic: str, language: str, rag_examples: list[dict], model_choice: str) -> dict | None:
    logger.info("IA Service: génération d'un plan de programmation pour %s", topic)
    examples_text = "\n\n".join(
        [f"Plan exemple pour '{ex['main_skill']}':\n{json.dumps(ex['plan'], ensure_ascii=False, indent=2)}" for ex in rag_examples]
    ) if rag_examples else ""

    system_prompt = f"""
Tu es un expert en pédagogie de la programmation. Construis un plan complet pour maîtriser "{topic}".

[CONTRAINTES]
- Retourne un objet JSON unique avec les clés "overview" et "levels".
- "overview" doit préciser:
  {{
    "target_language": "{language}",
    "audience": "profil apprenant",
    "prerequisites": ["liste de prérequis"]
  }}
- Chaque élément de "levels" doit contenir:
  {{
    "level_title": "Module en français",
    "focus": "objectif principal",
    "project": "mini-projet concret",
    "chapters": [
      {{"chapter_title": "Concepts & théorie"}},
      {{"chapter_title": "Guided practice et exemples"}},
      {{"chapter_title": "Challenge applicatif"}}
    ]
  }}
- Prévois entre 8 et 12 levels en montée progressive (bases syntaxiques, structures de contrôle, fonctions, modules, OOP, manipulation de données, automatisation, projet final, etc.).
- Mets l'accent sur des projets concrets (CLI, web, data, tests automatisés...).
- Style clair, actionnable, pas de listes vides.
"""

    if examples_text:
        system_prompt += f"\n\nPlans d'inspiration (ne rien copier mot à mot) :\n{examples_text}"

    user_prompt = "Produis le JSON demandé pour ce parcours de programmation."
    try:
        return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)
    except Exception as exc:
        logger.error("Erreur de génération de plan de programmation: %s", exc, exc_info=True)
        return None

def generate_adaptive_learning_plan(title: str, personalization_details: Dict[str, Any], model_choice: str) -> dict:
    user_context = json.dumps(personalization_details, ensure_ascii=False)
    system_prompt = prompt_manager.get_prompt("course_planning.adaptive_plan", user_context=user_context, ensure_json=True)
    try: return _call_ai_model_json(title, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur de plan de cours adapté pour '{title}': {e}")
        return {}

def generate_personalization_questions(title: str, model_choice: str) -> Dict[str, Any]:
    logger.info(f"IA - Génération des questions de personnalisation pour '{title}'")
    system_prompt = prompt_manager.get_prompt("course_planning.personalization_questions", title=title, ensure_json=True)
    user_prompt = f"Génère les questions de personnalisation pour un cours sur : {title}"
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
        if "fields" in data:
            for field in data["fields"]:
                if field.get("type") == "select" and "options" in field:
                    corrected = []
                    for opt in field["options"]:
                        if isinstance(opt, dict): corrected.append(opt)
                        else: corrected.append({"value": str(opt).lower().replace(" ", "_"), "label": str(opt)})
                    field["options"] = corrected
        if "fields" in data and isinstance(data["fields"], list): return data
        for key, value in data.items():
            if isinstance(value, list): return {"fields": value}
        raise ValueError("La réponse de l'IA ne contient aucune liste de champs valide.")
    except Exception as e:
        logger.error(f"Erreur de génération du formulaire pour '{title}': {e}", exc_info=True)
        return {"fields": []}

def generate_chapter_plan_for_level(level_title: str, model_choice: str, user_context: Optional[str] = None) -> List[str]:
    system_prompt = prompt_manager.get_prompt("generic_content.chapter_plan", user_context=user_context, ensure_json=True)
    try:
        data = _call_ai_model_json(level_title, model_choice, system_prompt=system_prompt)
        return data.get("chapters", []) or []
    except Exception as e:
        logger.error(f"Erreur de plan de chapitre pour '{level_title}': {e}")
        return []

def generate_lesson_for_chapter(chapter_title: str, model_choice: str) -> str:
    system_prompt = prompt_manager.get_prompt("generic_content.lesson", ensure_json=True)
    try:
        data = _call_ai_model_json(chapter_title, model_choice, system_prompt=system_prompt)
        return data.get("lesson_text", "") or ""
    except Exception as e:
        logger.error(f"Erreur de génération de leçon pour '{chapter_title}': {e}")
        return ""

def generate_exercises_for_lesson(db: Session, user: User, lesson_text: str, chapter_title: str, course_type: str, model_choice: str) -> List[Dict[str, Any]]:
    logger.info(f"Génération des exercices pour le chapitre '{chapter_title}' (Type: {course_type})")
    try:
        data = _call_ai_with_rag_examples(db=db, user=user, user_prompt=lesson_text, system_prompt_template="generic_content.exercises_rag", feature_name="exercise_generation", example_type="exercise", model_choice=model_choice, prompt_variables={"course_type": course_type, "chapter_title": chapter_title})
        exercises = (data.get("exercises") or data.get("items") or data.get("components") or [])
        norm = []
        for ex in exercises:
            if not isinstance(ex, dict): continue
            content = ex.get("content_json") or ex.get("content") or ex.get("data")
            if not content: continue
            norm.append({"title": ex.get("title", "Exercice"), "category": ex.get("category", chapter_title if 'chapter_title' in locals() else "General"), "component_type": ex.get("component_type", ex.get("type", "unknown")), "bloom_level": ex.get("bloom_level", "remember"), "content_json": content})
            return norm
    except Exception as e:
        logger.error(f"Erreur de génération d'exercices pour '{chapter_title}': {e}", exc_info=True)
        logger.error("Lorenzo Payload exercices inattendu (aperçu 1k): %s", str(data)[:1000])
        return []

def generate_language_pedagogical_content(course_title: str, chapter_title: str, model_choice: str, **kwargs) -> Dict[str, Any]:
    logger.info(f"IA Service: Génération du contenu pédagogique pour '{chapter_title}' (Cours: {course_title})")
    system_prompt = prompt_manager.get_prompt("language_generation.pedagogical_content", course_title=course_title, chapter_title=chapter_title, ensure_json=True, **kwargs)
    user_prompt = f"Génère le contenu pour le chapitre '{chapter_title}' du cours '{course_title}'."
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
        data["vocabulary"] = data.get("vocabulary") or []
        data["grammar"] = data.get("grammar") or []
        return data
    except Exception as e:
        logger.error(f"Erreur de génération de contenu pédagogique pour '{chapter_title}': {e}")
        return {"vocabulary": [], "grammar": []}

def generate_language_dialogue(course_title: str, chapter_title: str, vocabulary: list, grammar: list, model_choice: str, **kwargs) -> str:
    logger.info(f"IA Service: Génération du dialogue pour '{chapter_title}' (Cours: {course_title})")
    vocab_refs = ", ".join([f"{it.get('id','') or it.get('term','')}" for it in vocabulary])
    grammar_refs = ", ".join([f"{gr.get('id','') or gr.get('rule_name','')}" for gr in grammar])
    system_prompt = prompt_manager.get_prompt("language_generation.dialogue", course_title=course_title, chapter_title=chapter_title, target_cefr=kwargs.get("target_cefr", "A1"), max_turns=kwargs.get("max_turns", 8), include_transliteration=kwargs.get("include_transliteration"), include_french_gloss=kwargs.get("include_french_gloss"), vocab_refs=vocab_refs, grammar_refs=grammar_refs, ensure_json=True)
    try:
        data = _call_ai_model_json("Écris le dialogue maintenant.", model_choice, system_prompt=system_prompt)
        dlg = data.get("dialogue")
        if dlg is None: return "Erreur: Le dialogue n'a pas pu être généré."
        return json.dumps(dlg, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erreur de génération de dialogue pour '{chapter_title}': {e}")
        return "Le dialogue n'a pas pu être généré en raison d'une erreur technique."

def generate_writing_system_lesson(course_title: str, chapter_title: str, model_choice: str, **kwargs) -> str:
    logger.info(f"IA Service: Génération de la leçon théorique pour '{chapter_title}'")
    system_prompt = prompt_manager.get_prompt("language_generation.writing_system_lesson", course_title=course_title, chapter_title=chapter_title, ensure_json=True, **kwargs)
    user_prompt = "Rédige la leçon pour ce chapitre théorique."
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
        return data.get("lesson_text", "") or ""
    except Exception as e:
        logger.error(f"Erreur de génération de leçon théorique pour '{chapter_title}': {e}")
        return "Erreur lors de la génération de cette leçon."

def analyze_user_essay(prompt: str, guidelines: str, user_essay: str, model_choice: str) -> Dict[str, Any]:
    system_prompt = prompt_manager.get_prompt("analysis.analyze_essay", prompt=prompt, guidelines=guidelines, ensure_json=True)
    user_prompt = f"Voici l'essai : \"{user_essay}\""
    try: return _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de l'essai: {e}")
        return {"evaluation": "L'analyse a échoué.", "is_validated": False}

def start_ai_discussion(prompt: str, user_first_post: str, model_choice: str) -> Dict[str, Any]:
    system_prompt = prompt_manager.get_prompt("analysis.start_discussion", prompt=prompt, ensure_json=True)
    user_prompt = f"Première intervention de l'utilisateur : \"{user_first_post}\""
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
        data["history"] = [{"author": "user", "message": user_first_post}, {"author": "ia", "message": data.get("response_text")}]
        data["is_validated"] = False
        return data
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la discussion: {e}")
        return {"response_text": "Je n'ai pas bien compris. Pouvez-vous reformuler ?", "is_validated": False}

def continue_ai_discussion(prompt: str, history: List[Dict[str, str]], user_message: str, model_choice: str) -> Dict[str, Any]:
    history_str = "\n".join([f"{msg['author']}: {msg['message']}" for msg in history])
    system_prompt = prompt_manager.get_prompt("analysis.continue_discussion", prompt=prompt, history_str=history_str, ensure_json=True)
    user_prompt = f"Nouveau message de l'utilisateur : \"{user_message}\""
    try: return _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur lors de la continuation de la discussion: {e}")
        return {"response_text": "Je rencontre un problème technique.", "is_complete": False}

# --- NOUVELLE FONCTION POUR LE RAG ---
def generate_text_from_prompt(prompt: str, model_choice: str) -> str:
    """
    Fonction générique pour le RAG qui attend une réponse JSON et la retourne sous forme de chaîne.
    S'appuie sur la logique existante de _call_ai_model_json.
    """
    logger.info(f"Génération de texte (via JSON) avec le modèle : {model_choice} pour le RAG.")
    try:
        # Votre _call_ai_model_json est parfait car le prompt RAG demande déjà un JSON.
        # On le réutilise directement.
        json_response = _call_ai_model_json(
            user_prompt="Génère le plan de cours en respectant les instructions.", # User prompt simple
            system_prompt=prompt, # Le gros prompt RAG va dans le system_prompt
            model_choice=model_choice
        )
        # On reconvertit le JSON en chaîne de texte pour le reste du service
        return json.dumps(json_response, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erreur lors de l'appel RAG via _call_ai_model_json: {e}", exc_info=True)
        return "" # Retourner une chaîne vide en cas d'échec
    


#### ATOMS IA #####

def generate_contextual_lesson(
    course_plan_context: str,
    app_rules_context: str,
    target_lesson_title: str,
    model_choice: str,
    reference_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Génère le contenu d'une leçon (atomes) en utilisant un contexte riche.
    """
    logger.info(f"IA Service: Génération de contenu contextualisé pour '{target_lesson_title}'")
    
    # On assemble le prompt système à partir des différents contextes
    system_prompt = f"""
        Tu es un ingénieur pédagogique expert chargé de créer le contenu d'une leçon spécifique au sein d'un cours plus large.

        ---
        CONTEXTE GLOBAL DU COURS (PLAN COMPLET):
        {course_plan_context}
        ---
        INFORMATIONS SPÉCIFIQUES À NOTRE PLATEFORME:
        {app_rules_context}
        ---

        [INSTRUCTIONS IMPORTANTES]
        - Ton contenu doit se concentrer EXCLUSIVEMENT sur le titre de la leçon cible.
        - Ne déborde PAS sur les sujets des autres leçons listées dans le contexte global.
        - Ta réponse DOIT être un objet JSON unique contenant une clé "text" avec le contenu de la leçon.
        - Le texte doit être clair, engageant et rédigé en Markdown.
        - Tu dois vraiment donner le maximum de théorie avec des exemples si pertinent. NE PAS inclure d'exercices, de quiz ou de questions
    """
    if reference_text:
        system_prompt += (
            "\n        - Ta leçon doit rester fidèle aux extraits suivants issus du support fourni."
            " Cite explicitement lorsque pertinent.\n        ---\n        RESSOURCE À HONORER:\n"
            f"        {reference_text}\n        ---"
        )
    
    user_prompt = f"Génère le contenu pour la leçon : \"{target_lesson_title}\"."
    
    try:
        # On utilise votre fonction existante pour appeler l'IA et garantir un JSON
        return _call_ai_model_json(
            user_prompt=user_prompt, 
            model_choice=model_choice, 
            system_prompt=system_prompt
        )
    except Exception as e:
        logger.error(f"Erreur de génération de leçon contextualisée pour '{target_lesson_title}': {e}")
        # On renvoie un contenu d'erreur pour ne pas bloquer le flux
        return {"text": "Erreur lors de la génération du contenu de cette leçon."}
    

def generate_contextual_exercises(
    lesson_text: str,
    lesson_title: str,
    course_type: str, # ex: 'generic', 'philosophy', etc.
    difficulty: Optional[str], # <-- On ajoute le paramètre
    model_choice: str,
    reference_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Génère des exercices (ex: un QCM) basés sur le contenu d'une leçon fournie.
    """
    logger.info(f"IA Service: Génération d'exercices contextualisés pour '{lesson_title}'")
    difficulty_instruction = f"La difficulté de la question doit être : {difficulty}." if difficulty else "La difficulté doit être moyenne."

    system_prompt = f"""
Tu es un concepteur pédagogique chargé de créer des exercices de validation pour une leçon.

---
CONTENU DE LA LEÇON À ÉVALUER:
{lesson_text}
---

[INSTRUCTIONS IMPORTANTES]
- Crée un exercice de type QCM (Question à Choix Multiples) basé STRICTEMENT sur le contenu de la leçon fournie.
- La question doit être pertinente et tester une information clé de la leçon.
- Avoir un niveau de difficulté : {difficulty_instruction} basé sur la leçon
- Ta réponse DOIT être un objet JSON unique.
- Le JSON doit avoir la structure suivante :
  {{
    "question": "Ta question ici",
    "options": [
      {{"text": "Option 1", "is_correct": false}},
      {{"text": "Option 2", "is_correct": true}},
      {{"text": "Option 3", "is_correct": false}}
    ],
    "explanation": "Une brève explication de pourquoi la bonne réponse est correcte."
  }}
"""
    if reference_text:
        system_prompt += (
            "\n---\nRÉFÉRENCE À RESPECTER:\n"
            f"{reference_text}\n---"
        )
    
    user_prompt = f"Génère le QCM pour la leçon '{lesson_title}'."
    
    try:
        # On utilise votre fonction existante qui garantit un retour JSON
        return _call_ai_model_json(
            user_prompt=user_prompt,
            model_choice=model_choice,
            system_prompt=system_prompt
        )
    except Exception as e:
        logger.error(f"Erreur de génération d'exercices pour '{lesson_title}': {e}")
        return {} # On renvoie un objet vide en cas d'erreur


def generate_programming_lesson(
    course_plan_context: str,
    lesson_title: str,
    language: str,
    model_choice: str,
    reference_text: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info("IA Service: génération de leçon orientée programmation pour %s", lesson_title)
    system_prompt = f"""
Tu es un mentor de programmation. Crée une leçon complète en Markdown pour la leçon "{lesson_title}".

---
CONTEXTE DU COURS:
{course_plan_context}
---

[INSTRUCTIONS]
- Langage ciblé : {language}.
- La réponse DOIT être un objet JSON unique {{"text": "contenu markdown"}}.
- Structure recommandée : introduction, objectifs, explications progressives, blocs de code commentés, bonnes pratiques, questions de réflexion.
- Inclue au moins un bloc de code clé (en {language}) et une courte section "À retenir".
- Évite les projets complets ici (ce sera couvert dans les autres atomes).
"""
    if reference_text:
        system_prompt += (
            "\n---\nRÉFÉRENTIEL FOURNI:\n"
            f"{reference_text}\n---"
        )
    user_prompt = f"Rédige la leçon détaillée pour '{lesson_title}'."
    try:
        return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)
    except Exception as exc:
        logger.error("Erreur de génération de leçon programmation: %s", exc, exc_info=True)
        return {"text": "Erreur lors de la génération de cette leçon."}


def generate_code_example(
    lesson_text: str,
    lesson_title: str,
    language: str,
    model_choice: str,
) -> Dict[str, Any]:
    logger.info(f"IA Service: génération d'exemple de code pour '{lesson_title}'")
    system_prompt = f"""
Tu es un mentor de programmation. À partir de la leçon suivante, crée un exemple de code concis, exploitable et bien commenté.

---
LEÇON:
{lesson_text}
---

[INSTRUCTIONS]
- Utilise le langage: {language}.
- Retourne un objet JSON unique avec la structure:
  {{
    "description": "expliquer ce que montre l'exemple",
    "language": "{language}",
    "code": "code exécutable et commenté",
    "explanation": "analyse du code, bonnes pratiques"
  }}
- Reste fidèle au contenu de la leçon.
"""
    user_prompt = f"Crée un exemple de code pédagogique pour la leçon '{lesson_title}'."
    try:
        return _call_ai_model_json(
            user_prompt=user_prompt,
            model_choice=model_choice,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error(f"Erreur de génération d'exemple de code pour '{lesson_title}': {exc}")
        return None


def generate_code_challenge(
    lesson_text: str,
    lesson_title: str,
    language: str,
    model_choice: str,
) -> Dict[str, Any]:
    logger.info(f"IA Service: génération de challenge pour '{lesson_title}'")
    system_prompt = f"""
Tu es un concepteur d'exercices de programmation. À partir de la leçon ci-dessous, propose un challenge pratique.

---
LEÇON:
{lesson_text}
---

[INSTRUCTIONS]
- Langage utilisé : {language}.
- Retourne un objet JSON unique de la forme :
  {{
    "title": "titre court",
    "description": "consignes détaillées",
    "language": "{language}",
    "starter_code": "code de départ minimal",
    "sample_tests": [
      {{"input": "", "output": ""}}
    ],
    "hints": ["indice optionnel"]
  }}
- Le challenge doit être atteignable en moins d'une heure et aligné avec la leçon.
"""
    user_prompt = f"Génère un challenge de code pour la leçon '{lesson_title}'."
    try:
        return _call_ai_model_json(
            user_prompt=user_prompt,
            model_choice=model_choice,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error(f"Erreur de génération de challenge pour '{lesson_title}': {exc}")
        return None


def generate_code_sandbox_setup(
    lesson_title: str,
    language: str,
    stage: Dict[str, Any],
    model_choice: str,
) -> Dict[str, Any]:
    logger.info(f"IA Service: génération des consignes sandbox pour '{lesson_title}'")
    stage_json = json.dumps(stage, ensure_ascii=False)
    system_prompt = f"""
Tu es architecte d'environnements pédagogiques sécurisés.
Prépare une fiche d'onboarding pour un IDE/terminal côté client.

[Contexte de progression]
{stage_json}

[Contraintes]
- Rappelle que le code s'exécute uniquement dans un bac à sable isolé côté apprenant.
- Interdis explicitement l'envoi ou le collage de code dans la plateforme.
- Fournis 3 étapes de mise en route et 2 à 3 commandes de test adaptées au langage {language}.
- Ajoute un bloc "security" avec le champ booléen "code_submission_allowed": false.
- Ajoute un champ "checklist" avec 3 validations rapides avant de commencer le projet.
- Insère l'objet ci-dessus EXACTEMENT dans "progression_stage": {stage_json}
- Réponds avec un UNIQUE objet JSON conforme.

Format JSON attendu :
{{
  "title": "...",
  "language": "{language}",
  "difficulty": "...",
  "progression_stage": {stage_json},
  "workspace": {{
    "recommended_mode": "terminal+éditeur intégré",
    "setup_steps": ["..."],
    "commands_to_try": ["..."]
  }},
  "security": {{
    "code_submission_allowed": false,
    "sandbox_mode": "client_isolated",
    "safe_usage_guidelines": ["..."]
  }},
  "checklist": ["..."]
}}
"""
    user_prompt = f"Prépare les instructions d'ouverture du bac à sable pour la leçon '{lesson_title}'."
    try:
        return _call_ai_model_json(
            user_prompt=user_prompt,
            model_choice=model_choice,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error(f"Erreur de génération de sandbox pour '{lesson_title}': {exc}")
        return None


def generate_code_project_brief(
    lesson_text: str,
    lesson_title: str,
    language: str,
    stage: Dict[str, Any],
    model_choice: str,
) -> Dict[str, Any]:
    logger.info(f"IA Service: génération de projet de validation pour '{lesson_title}'")
    stage_json = json.dumps(stage, ensure_ascii=False)
    system_prompt = f"""
Tu es mentor senior de programmation.
À partir de la leçon et du contexte ci-dessous, conçois un mini-projet progressif.

Leçon :
{lesson_text}

Progression :
{stage_json}

[Contraintes]
- Le projet doit correspondre à la progression indiquée.
- Fournis un résumé, 3 objectifs pédagogiques, des jalons ("milestones") avec étapes concrètes.
- Ajoute un bloc "deliverables" listant les livrables attendus.
- Ajoute un bloc "validation" avec "self_checklist" et "suggested_tests".
- Ajoute une section "security" rappelant de ne jamais envoyer son code ("code_submission_allowed": false).
- Propose 1 à 2 "extension_ideas" optionnelles.
- Insère l'objet de progression EXACT dans "progression_stage": {stage_json}
- Réponds avec un SEUL objet JSON.

Structure attendue :
{{
  "title": "...",
  "summary": "...",
  "language": "{language}",
  "difficulty": "...",
  "progression_stage": {stage_json},
  "objectives": ["..."],
  "milestones": [{{"label": "...", "steps": ["..."]}}],
  "deliverables": ["..."],
  "validation": {{
    "self_checklist": ["..."],
    "suggested_tests": ["..."]
  }},
  "security": {{
    "code_submission_allowed": false,
    "reminders": ["..."]
  }},
  "extension_ideas": ["..."]
}}
"""
    user_prompt = f"Crée un projet de validation pour la leçon '{lesson_title}'."
    try:
        return _call_ai_model_json(
            user_prompt=user_prompt,
            model_choice=model_choice,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error(f"Erreur de génération de projet pour '{lesson_title}': {exc}")
        return None


def generate_live_code_session(
    lesson_text: str,
    lesson_title: str,
    language: str,
    challenge: Dict[str, Any],
    model_choice: str,
) -> Dict[str, Any]:
    logger.info(f"IA Service: génération de session interactive pour '{lesson_title}'")
    challenge_json = json.dumps(challenge, ensure_ascii=False) if challenge else "{}"
    system_prompt = f"""
Tu aides l'utilisateur à pratiquer dans un éditeur de code intégré.

Leçon :
{lesson_text}

Challenge de référence :
{challenge_json}

Retourne un objet JSON unique :
{{
  "language": "{language}",
  "instructions": "guides pas à pas",
  "starter_code": "code initial",
  "hints": ["indice"],
  "suggested_experiments": ["idées pour aller plus loin"]
}}
"""
    user_prompt = f"Prépare une session d'entraînement interactive pour la leçon '{lesson_title}'."
    try:
        return _call_ai_model_json(
            user_prompt=user_prompt,
            model_choice=model_choice,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.error(f"Erreur de génération de session interactive pour '{lesson_title}': {exc}")
        return None

# ---------------------------------------------------------------------------
# Générateurs d'exercices scientifiques / mathématiques
# ---------------------------------------------------------------------------

def generate_fill_in_blank_exercise(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Tu es un concepteur pédagogique en sciences. À partir du texte fourni, crée un exercice de texte à trous.

Contraintes :
- Utilise entre 2 et 4 blancs au format {{1}}, {{2}}, etc.
- Les blancs doivent correspondre à des mots ou expressions clés issus du texte.
- Fournis un JSON respectant exactement la structure :
  {{
    "prompt": "...",
    "text": "Phrase avec {{1}} et {{2}}",
    "blanks": [{{"answers": ["réponse", "synonyme"]}}]
  }}
"""
    user_prompt = f"Génère un texte à trous pour le thème '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)

def generate_short_answer_exercise(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Crée une question à réponse courte en t'appuyant exclusivement sur le texte. Donne 2 ou 3 formulations acceptées.

JSON attendu :
{{"prompt": "Question ouverte", "acceptable_answers": ["réponse1", "réponse2"], "explanation": "Justification"}}
"""
    user_prompt = f"Rédige une question courte sur '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)

def generate_true_false_exercise(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Crée une affirmation vraie ou fausse vérifiable grâce au texte.

JSON : {{"statement": "...", "correct_answer": true/false, "explanation": "..."}}
"""
    user_prompt = f"Produit un exercice Vrai/Faux sur '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)

def generate_matching_exercise(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Crée un exercice d'association terme/définition (3 à 5 paires).

JSON : {{"prompt": "...", "pairs": [{{"left": "Terme", "right": "Définition"}}]}}
"""
    user_prompt = f"Conçois un appariement pour '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)

def generate_ordering_exercise(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Crée un exercice d'ordonnancement de 4 à 6 étapes décrivant une procédure du texte.

JSON : {{"prompt": "...", "items": ["Étape 1", "Étape 2"]}}
"""
    user_prompt = f"Propose un exercice d'ordonnancement pour '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)

def generate_flashcards(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Génère 3 à 5 flashcards couvrant définitions, exemples et points de vigilance.

JSON : {{"prompt": "...", "cards": [{{"front": "Question", "back": "Réponse"}}]}}
"""
    user_prompt = f"Crée des flashcards sur '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)

def generate_categorization_exercise(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Conçois un exercice de classification avec 2 ou 3 catégories et 4 à 6 items.

JSON : {{"prompt": "...", "categories": [{{"id": "cat1", "label": "Nom"}}], "items": [{{"id": "item1", "label": "Texte", "correct_category": "cat1"}}]}}
"""
    user_prompt = f"Prépare une activité de classification pour '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)

def generate_diagram_completion(
    lesson_text: str,
    topic: str,
    model_choice: str,
) -> Dict[str, Any]:
    system_prompt = f"""
Crée un schéma à compléter comportant 2 à 4 zones (slots) avec options et bonne réponse.

JSON : {{"title": "...", "description": "...", "slots": [{{"id": "slot1", "label": "Zone", "options": [{{"value": "opt1", "label": "Option"}}], "correct_option": "opt1"}}]}}
"""
    user_prompt = f"Propose un schéma à compléter pour '{topic}'.\n\n{lesson_text}"
    return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)


def generate_classification_metadata(
    topic: str,
    domain: str,
    area: str,
    model_choice: str = "gpt-5-mini-2025-08-07",
) -> Dict[str, Any]:
    """Crée une courte description pour un couple domaine / sous-domaine."""

    system_prompt = """
Tu gères une taxonomie de capsules éducatives. À partir des informations fournies,
produis un objet JSON décrivant brièvement le domaine et le sous-domaine, avec quelques exemples.

Format obligatoire :
{
  "domain_description": "Phrase concise décrivant le domaine.",
  "area_description": "Phrase concise décrivant le sous-domaine.",
  "sample_topics": ["exemple 1", "exemple 2"]
}

Les phrases doivent être en français, claires et adaptées à un catalogue pédagogique.
"""

    user_prompt = (
        f"Texte initial : {topic}\n"
        f"Domaine retenu : {domain}\n"
        f"Sous-domaine retenu : {area}\n"
        "Rédige l'objet JSON demandé."
    )

    try:
        return _call_ai_model_json(user_prompt=user_prompt, model_choice=model_choice, system_prompt=system_prompt)
    except Exception as exc:  # pragma: no cover - tolérance de défaillance
        logger.error("Erreur lors de la génération de métadonnées de classification: %s", exc, exc_info=True)
        return {}
