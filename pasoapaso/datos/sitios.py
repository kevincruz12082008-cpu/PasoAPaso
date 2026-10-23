SITIOS = {
    "google": ("Google", "google.com"),
    "facebook": ("Facebook", "facebook.com"),
    "gmail": ("Gmail", "mail.google.com"),
    "correo": ("Gmail", "mail.google.com"),
    "whatsapp web": ("WhatsApp Web", "web.whatsapp.com"),
    "instagram": ("Instagram", "instagram.com"),
    "tiktok": ("TikTok", "tiktok.com"),
    "netflix": ("Netflix", "netflix.com"),
    "wikipedia": ("Wikipedia", "es.wikipedia.org"),
    "classroom": ("Google Classroom", "classroom.google.com"),
    "google classroom": ("Google Classroom", "classroom.google.com"),
    "drive": ("Google Drive", "drive.google.com"),
    "google drive": ("Google Drive", "drive.google.com"),
    "traductor": ("Google Traductor", "translate.google.com"),
    "mapas": ("Google Maps", "maps.google.com"),
    "google maps": ("Google Maps", "maps.google.com"),
    "claude": ("Claude", "claude.ai"),
}


def buscar_sitio(texto):
    return SITIOS.get(texto.strip())
