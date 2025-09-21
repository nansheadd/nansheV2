from jinja2 import Template

BASE_WRAPPER = """
<div style=\"font-family:Inter,Arial,sans-serif;font-size:16px;line-height:1.6\">
  <h2 style=\"margin:0 0 8px\">Nanshe</h2>
  {{ body }}
</div>
"""

CONFIRM_HTML = Template(BASE_WRAPPER)

RESET_HTML = Template(BASE_WRAPPER)

REPORT_ACK_HTML = Template(BASE_WRAPPER)

L = {
  "fr": {
    "confirm": {
      "subject": "Confirme ton compte",
      "lead": "Clique sur le bouton pour confirmer ton e‑mail et activer ton compte.",
      "cta": "Confirmer mon compte",
      "ignore": "Si tu n’es pas à l’origine de cette demande, ignore cet e‑mail."
    },
    "reset": {
      "subject": "Réinitialise ton mot de passe",
      "lead": "Clique sur le bouton pour définir un nouveau mot de passe. Le lien expire dans 30 minutes.",
      "cta": "Réinitialiser le mot de passe",
      "ignore": "Si tu n’es pas à l’origine de cette demande, ignore cet e‑mail."
    },
    "report_ack": {
      "subject": "Nous avons bien reçu ton signalement",
      "lead": "Merci d’avoir signalé un contenu. Nous allons vérifier les informations transmises.",
      "summary_intro": "Résumé de ton signalement",
      "url_label": "Contenu signalé",
      "reason_label": "Motif",
      "name_label": "Nom fourni",
      "good_faith_label": "Déclaration sur l'honneur",
      "good_faith_yes": "Acceptée",
      "good_faith_no": "Non fournie",
      "anonymous": "Anonyme",
      "closing": "Tu recevras un suivi si des informations complémentaires sont nécessaires."
    }
  },
  "en": {
    "confirm": {
      "subject": "Confirm your account",
      "lead": "Click the button below to confirm your email and activate your account.",
      "cta": "Confirm my account",
      "ignore": "If you did not request this, you can safely ignore this email."
    },
    "reset": {
      "subject": "Reset your password",
      "lead": "Click the button to set a new password. The link expires in 30 minutes.",
      "cta": "Reset password",
      "ignore": "If you did not request this, you can ignore this email."
    },
    "report_ack": {
      "subject": "We received your report",
      "lead": "Thanks for flagging this content. Our team will review the details you shared.",
      "summary_intro": "What you submitted",
      "url_label": "Reported content",
      "reason_label": "Reason",
      "name_label": "Name provided",
      "good_faith_label": "Good-faith declaration",
      "good_faith_yes": "Provided",
      "good_faith_no": "Missing",
      "anonymous": "Anonymous",
      "closing": "We will reach out if we need more information."
    }
  },
  "nl": {
    "confirm": {
      "subject": "Bevestig je account",
      "lead": "Klik op de knop om je e‑mail te bevestigen en je account te activeren.",
      "cta": "Mijn account bevestigen",
      "ignore": "Als jij dit niet hebt aangevraagd, kun je deze e‑mail negeren."
    },
    "reset": {
      "subject": "Wachtwoord resetten",
      "lead": "Klik op de knop om een nieuw wachtwoord in te stellen. De link verloopt binnen 30 minuten.",
      "cta": "Wachtwoord resetten",
      "ignore": "Als jij dit niet hebt aangevraagd, kun je deze e‑mail negeren."
    },
    "report_ack": {
      "subject": "We hebben je melding ontvangen",
      "lead": "Bedankt om deze inhoud te melden. We bekijken de informatie die je hebt doorgestuurd.",
      "summary_intro": "Overzicht van je melding",
      "url_label": "Gerapporteerde inhoud",
      "reason_label": "Reden",
      "name_label": "Opgegeven naam",
      "good_faith_label": "Verklaring te goeder trouw",
      "good_faith_yes": "Bevestigd",
      "good_faith_no": "Ontbreekt",
      "anonymous": "Anoniem",
      "closing": "We nemen contact op als we bijkomende informatie nodig hebben."
    }
  }
}

def render_confirm(url: str, lang: str):
  m = L.get(lang, L["fr"])['confirm']
  body = f"""
  <p>{m['lead']}</p>
  <p><a href=\"{url}\" style=\"display:inline-block;padding:10px 16px;border-radius:8px;background:#7c3aed;color:#fff;text-decoration:none\">{m['cta']}</a></p>
  <p style=\"color:#6b7280;font-size:12px\">{m['ignore']}</p>
  """
  return m['subject'], CONFIRM_HTML.render(body=body)

def render_reset(url: str, lang: str):
  m = L.get(lang, L["fr"])['reset']
  body = f"""
  <p>{m['lead']}</p>
  <p><a href=\"{url}\" style=\"display:inline-block;padding:10px 16px;border-radius:8px;background:#7c3aed;color:#fff;text-decoration:none\">{m['cta']}</a></p>
  <p style=\"color:#6b7280;font-size:12px\">{m['ignore']}</p>
  """
  return m['subject'], RESET_HTML.render(body=body)

def render_report_ack(payload: dict, lang: str):
  messages = L.get(lang, L["fr"])['report_ack']
  body = f"""
  <p>{messages['lead']}</p>
  <p style=\"margin:16px 0 8px;font-weight:600\">{messages['summary_intro']}</p>
  <ul style=\"padding-left:20px;margin:0 0 16px\">
    <li><strong>{messages['url_label']}</strong>: {payload.get('url')}</li>
    <li><strong>{messages['reason_label']}</strong>: {payload.get('reason')}</li>
    <li><strong>{messages['name_label']}</strong>: {payload.get('name') or messages['anonymous']}</li>
    <li><strong>{messages['good_faith_label']}</strong>: {messages['good_faith_yes'] if payload.get('good_faith') else messages['good_faith_no']}</li>
  </ul>
  <p>{messages['closing']}</p>
  """
  return messages['subject'], REPORT_ACK_HTML.render(body=body)
