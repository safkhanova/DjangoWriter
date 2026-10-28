"""
emailotp_translations.py — every string the emailotp package emits, in az/en/it.

Merge into your existing loader:

    from emailotp.emailotp_translations import EMAILOTP_TRANSLATIONS
    TRANSLATIONS.update(EMAILOTP_TRANSLATIONS)

Keys are namespaced `emailotp.*` so they never collide with the project's own.
Three groups:
  emailotp.msg.*    — messages framework strings raised from views.py
  emailotp.form.*   — field labels and validation errors from forms.py
  emailotp.<page>.* — page text from the templates
  emailotp.email.*  — outgoing email text
"""

EMAILOTP_TRANSLATIONS = {

    # ---------- Python messages (views.py) ----------
    "emailotp.msg.code_expired": {
        "az": "Kod artıq etibarlı deyil. Yeni kod istəyin.",
        "en": "That code is no longer valid. Request a new one.",
        "it": "Il codice non è più valido. Richiedine uno nuovo.",
    },
    "emailotp.msg.too_many_wrong": {
        "az": "Çox sayda yanlış cəhd. Yeni kod istəyin.",
        "en": "Too many wrong attempts. Request a new code.",
        "it": "Troppi tentativi errati. Richiedi un nuovo codice.",
    },
    "emailotp.msg.code_wrong": {
        "az": "Kod yanlışdır.",
        "en": "That code is not correct.",
        "it": "Il codice non è corretto.",
    },
    "emailotp.msg.throttled": {
        "az": "Çox sayda cəhd. Bir az sonra yenidən cəhd edin.",
        "en": "Too many attempts. Try again later.",
        "it": "Troppi tentativi. Riprova più tardi.",
    },
    "emailotp.msg.email_confirmed": {
        "az": "Email təsdiqləndi! İndi daxil ola bilərsiniz.",
        "en": "Email confirmed. You can now sign in.",
        "it": "Email confermata. Ora puoi accedere.",
    },
    "emailotp.msg.resent": {
        "az": "Əgər ünvan düzgündürsə, yeni kod göndərildi.",
        "en": "If the address is correct, a new code has been sent.",
        "it": "Se l'indirizzo è corretto, è stato inviato un nuovo codice.",
    },
    "emailotp.msg.password_wrong": {
        "az": "Şifrə yanlışdır.",
        "en": "That password is not correct.",
        "it": "La password non è corretta.",
    },

    # ---------- Form labels and errors (forms.py) ----------
    "emailotp.form.name": {
        "az": "Ad*",
        "en": "Name*",
        "it": "Nome*",
    },
    "emailotp.form.email": {
        "az": "Email*",
        "en": "Email*",
        "it": "Email*",
    },
    "emailotp.form.password": {
        "az": "Şifrə*",
        "en": "Password*",
        "it": "Password*",
    },
    "emailotp.form.password2": {
        "az": "Şifrə (təkrar)*",
        "en": "Password (again)*",
        "it": "Password (ripeti)*",
    },
    "emailotp.form.code": {
        "az": "6 rəqəmli kod*",
        "en": "6-digit code*",
        "it": "Codice a 6 cifre*",
    },
    "emailotp.form.remember": {
        "az": "Məni xatırla",
        "en": "Remember me",
        "it": "Ricordami",
    },
    "emailotp.form.password_mismatch": {
        "az": "Şifrələr eyni deyil.",
        "en": "The two passwords do not match.",
        "it": "Le due password non coincidono.",
    },
    "emailotp.form.code_digits": {
        "az": "Kod {n} rəqəmdən ibarətdir.",
        "en": "The code is {n} digits.",
        "it": "Il codice è di {n} cifre.",
    },

    # ---------- Register page ----------
    "emailotp.register.title": {
        "az": "Qeydiyyat",
        "en": "Register",
        "it": "Registrazione",
    },
    "emailotp.register.subtitle": {
        "az": "Qeydiyyatdan sonra email ünvanınıza 6 rəqəmli təsdiq kodu göndəriləcək.",
        "en": "We'll email you a 6-digit confirmation code to finish signing up.",
        "it": "Ti invieremo un codice di conferma a 6 cifre per completare la registrazione.",
    },
    "emailotp.register.submit": {
        "az": "Qeydiyyatdan keç",
        "en": "Register",
        "it": "Registrati",
    },
    "emailotp.register.have_account": {
        "az": "Artıq hesabınız var?",
        "en": "Already have an account?",
        "it": "Hai già un account?",
    },
    "emailotp.register.login_here": {
        "az": "Daxil olmaq üçün buraya klikləyin",
        "en": "Sign in",
        "it": "Accedi",
    },

    # ---------- Register verify page ----------
    "emailotp.register_verify.title": {
        "az": "Email təsdiqi",
        "en": "Confirm your email",
        "it": "Conferma la tua email",
    },
    "emailotp.register_verify.submit": {
        "az": "Təsdiqlə",
        "en": "Confirm",
        "it": "Conferma",
    },

    # ---------- Shared verify strings ----------
    "emailotp.verify.sent_to": {
        "az": "Kodu bu ünvana göndərdik:",
        "en": "We sent a code to:",
        "it": "Abbiamo inviato un codice a:",
    },
    "emailotp.verify.resend": {
        "az": "Kodu yenidən göndər",
        "en": "Send a new code",
        "it": "Invia un nuovo codice",
    },

    # ---------- Login page ----------
    "emailotp.login.title": {
        "az": "Daxil ol",
        "en": "Sign in",
        "it": "Accedi",
    },
    "emailotp.login.subtitle": {
        "az": "Email ünvanınızı daxil edin — sizə 6 rəqəmli birdəfəlik kod göndərəcəyik. Şifrə lazım deyil.",
        "en": "Enter your email address and we'll send you a one-time code. No password needed.",
        "it": "Inserisci il tuo indirizzo email e ti invieremo un codice monouso. Nessuna password richiesta.",
    },
    "emailotp.login.remember": {
        "az": "Məni xatırla — 30 gün, əks halda 24 saat",
        "en": "Remember me — 30 days, otherwise 24 hours",
        "it": "Ricordami — 30 giorni, altrimenti 24 ore",
    },
    "emailotp.login.submit": {
        "az": "Kod göndər",
        "en": "Send code",
        "it": "Invia codice",
    },
    "emailotp.login.no_account": {
        "az": "Hələ hesabınız yoxdur?",
        "en": "No account yet?",
        "it": "Non hai ancora un account?",
    },
    "emailotp.login.register_here": {
        "az": "Qeydiyyatdan keçmək üçün bura klikləyin",
        "en": "Register",
        "it": "Registrati",
    },

    # ---------- Login password page (staff) ----------
    "emailotp.login_password.title": {
        "az": "Şifrə",
        "en": "Password",
        "it": "Password",
    },
    "emailotp.login_password.subtitle": {
        "az": "Bu hesab üçün şifrə tələb olunur:",
        "en": "This account also requires a password:",
        "it": "Questo account richiede anche una password:",
    },
    "emailotp.login_password.submit": {
        "az": "Davam et",
        "en": "Continue",
        "it": "Continua",
    },

    # ---------- Login verify page ----------
    "emailotp.login_verify.title": {
        "az": "Təsdiq kodu",
        "en": "Enter your code",
        "it": "Inserisci il codice",
    },
    "emailotp.login_verify.submit": {
        "az": "Daxil ol",
        "en": "Sign in",
        "it": "Accedi",
    },

    # ---------- Outgoing email ----------
    "emailotp.email.greeting": {
        "az": "Salam!",
        "en": "Hello!",
        "it": "Ciao!",
    },
    "emailotp.email.code_subject": {
        "az": "Təsdiq kodu",
        "en": "Verification code",
        "it": "Codice di verifica",
    },
    "emailotp.email.code_intro": {
        "az": "Təsdiq kodunuz —",
        "en": "Your verification code for",
        "it": "Il tuo codice di verifica per",
    },
    "emailotp.email.code_validity": {
        "az": "Kod etibarlıdır:",
        "en": "The code is valid for",
        "it": "Il codice è valido per",
    },
    "emailotp.email.minutes": {
        "az": "dəqiqə ərzində.",
        "en": "minutes.",
        "it": "minuti.",
    },
    "emailotp.email.ignore": {
        "az": "Əgər bu cəhdi siz etməmisinizsə, bu məktubu nəzərə almayın.",
        "en": "If you did not request this, you can ignore this message.",
        "it": "Se non hai richiesto tu questa operazione, ignora questo messaggio.",
    },
    "emailotp.email.exists_subject": {
        "az": "Hesabınız artıq mövcuddur",
        "en": "You already have an account",
        "it": "Hai già un account",
    },
    "emailotp.email.exists_intro": {
        "az": "Bu email ünvanı ilə qeydiyyatdan keçmək cəhdi oldu, lakin hesab artıq mövcuddur —",
        "en": "Someone tried to register an account with this email address, but an account already exists on",
        "it": "Qualcuno ha provato a registrarsi con questo indirizzo email, ma un account esiste già su",
    },
    "emailotp.email.exists_login": {
        "az": "Daxil olmaq üçün:",
        "en": "To sign in:",
        "it": "Per accedere:",
    },
    "emailotp.msg.send_failed": {
        "az": "Kod hazırda göndərilə bilmədi. Bir az sonra yenidən cəhd edin.",
        "en": "We couldn't send the code right now. Please try again in a moment.",
        "it": "Non è stato possibile inviare il codice al momento. Riprova tra poco.",
    },
}