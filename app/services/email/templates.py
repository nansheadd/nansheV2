from jinja2 import Template

CONFIRM_HTML = Template("""
<div style="font-family:Inter,Arial,sans-serif;font-size:16px;line-height:1.6">
  <h2 style="margin:0 0 8px">Nanshe</h2>
  <p>{{ lead }}</p>
  <p>
    <a href="{{ url }}" style="display:inline-block;padding:10px 16px;border-radius:8px;background:#7c3aed;color:#fff;text-decoration:none">{{ cta }}</a>
  </p>
  <p style="color:#6b7280;font-size:12px">{{ ignore }}</p>
</div>
""")

RESET_HTML = Template("""
<div style="font-family:Inter,Arial,sans-serif;font-size:16px;line-height:1.6">
  <h2 style="margin:0 0 8px">Nanshe</h2>
  <p>{{ lead }}</p>
  <p>
    <a href="{{ url }}" style="display:inline-block;padding:10px 16px;border-radius:8px;background:#7c3aed;color:#fff;text-decoration:none">{{ cta }}</a>
  </p>
  <p style="color:#6b7280;font-size:12px">{{ ignore }}</p>
</div>
""")

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
    }
  }
}

def render_confirm(url: str, lang: str):
  m = L.get(lang, L["fr"])['confirm']
  return m['subject'], CONFIRM_HTML.render(lead=m['lead'], cta=m['cta'], ignore=m['ignore'], url=url)

def render_reset(url: str, lang: str):
  m = L.get(lang, L["fr"])['reset']
  return m['subject'], RESET_HTML.render(lead=m['lead'], cta=m['cta'], ignore=m['ignore'], url=url)