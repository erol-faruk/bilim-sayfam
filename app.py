import os
import sqlite3
import threading
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import resend
from flask import Flask, render_template, request, redirect, url_for, session, flash

load_dotenv()

# Cloudinary Yapılandırması
cloudinary.config(
    cloudinary_url=os.environ.get('CLOUDINARY_URL')
)

# Resend API Yapılandırması (Port Engellerini Aşar)
resend.api_key = os.environ.get('RESEND_API_KEY')

app = Flask(__name__)
app.secret_key = "super_gizli_yonetici_anahtari"
YONETICI_SIFRESI = "123456"
VERITABANI = "bilim_v2.db"

# Arka planda Resend HTTP API ile e-posta gönderimi
def eposta_gonder_arkaplan(baslik, alici_listesi):
    try:
        print("--- MAIL GONDERIMI BASLADILDI (RESEND API) ---")
        
        # Gönderici adresi olarak Resend varsayılan veya onaylı adresiniz
        sender_email = "onboarding@resend.dev"
        admin_email = os.environ.get('MAIL_USERNAME', 'eavci1987@gmail.com')

        params = {
            "from": f"Bilim Sayfam <{sender_email}>",
            "to": [admin_email],
            "subject": f"Yeni Yayın: {baslik}",
            "html": f"""
                <h3>Merhaba!</h3>
                <p>Sitemizde yeni bir bilimsel içerik paylaşıldı:</p>
                <p><strong>Başlık:</strong> {baslik}</p>
                <p><a href="https://bilim-sayfam-1.onrender.com">Sitemize gitmek için tıklayın</a></p>
            """
        }

        if alici_listesi:
            params["bcc"] = alici_listesi

        r = resend.Emails.send(params)
        print(f"--- MAIL BASARIYLA GONDERILDI: {r} ---")
    except Exception as e:
        print(f"--- MAIL GONDERME HATASI: {e} ---")

def veritabani_hazirla():
    baglanti = sqlite3.connect(VERITABANI)
    cursor = baglanti.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aboneler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            eposta TEXT UNIQUE NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS makaleler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            icerik TEXT,
            dosya_url TEXT,
            dosya_turu TEXT,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS yorumlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            makale_id INTEGER NOT NULL,
            yazar TEXT NOT NULL,
            yorum TEXT NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (makale_id) REFERENCES makaleler (id) ON DELETE CASCADE
        )
    """)

    baglanti.commit()
    baglanti.close()

veritabani_hazirla()

@app.route('/')
def index():
    baglanti = sqlite3.connect(VERITABANI)
    baglanti.row_factory = sqlite3.Row
    cursor = baglanti.cursor()

    makaleler = cursor.execute("SELECT * FROM makaleler ORDER BY id DESC").fetchall()

    makale_listesi = []
    for m in makaleler:
        yorumlar = cursor.execute("SELECT * FROM yorumlar WHERE makale_id = ? ORDER BY id DESC", (m['id'],)).fetchall()
        makale_listesi.append({
            'makale': m,
            'yorumlar': yorumlar
        })

    baglanti.close()
    return render_template('index.html', makaleler=makale_listesi)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sifre = request.form.get('password')
        if sifre == YONETICI_SIFRESI:
            session['admin'] = True
            flash('Başarıyla giriş yapıldı!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Hatalı şifre!', 'danger')
            return redirect(url_for('login'))

    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Yönetici Girişi</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light d-flex align-items-center justify-content-center" style="height: 100vh;">
        <div class="card p-4 shadow-sm" style="max-width: 400px; width: 100%;">
            <h4 class="card-title text-center mb-3">Yönetici Girişi</h4>
            <form action="/login" method="POST">
                <div class="mb-3">
                    <input type="password" name="password" class="form-control" placeholder="Yönetici Şifresi" required autocomplete="off">
                </div>
                <button type="submit" class="btn btn-primary w-100">Giriş Yap</button>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('index'))

@app.route('/makale-ekle', methods=['POST'])
def makale_ekle():
    if not session.get('admin'):
        return redirect(url_for('index'))

    baslik = request.form.get('baslik')
    icerik = request.form.get('icerik')
    dosya = request.files.get('dosya')

    dosya_url = None
    dosya_turu = None

    if dosya and dosya.filename != '':
        try:
            yukleme_sonucu = cloudinary.uploader.upload(dosya, resource_type="auto")
            dosya_url = yukleme_sonucu.get('secure_url')
            dosya_turu = yukleme_sonucu.get('resource_type')
        except Exception as e:
            flash(f'Dosya yükleme hatası: {str(e)}', 'danger')
            return redirect(url_for('index'))

    baglanti = sqlite3.connect(VERITABANI)
    baglanti.execute("INSERT INTO makaleler (baslik, icerik, dosya_url, dosya_turu) VALUES (?, ?, ?, ?)",
                     (baslik, icerik, dosya_url, dosya_turu))
    baglanti.commit()
    baglanti.close()

    # Otomatik Mail Gönderimi (HTTP API + Threading)
    try:
        baglanti_mail = sqlite3.connect(VERITABANI)
        cursor = baglanti_mail.cursor()
        cursor.execute("SELECT eposta FROM aboneler")
        aboneler = cursor.fetchall()
        baglanti_mail.close()

        alici_listesi = [abone[0] for abone in aboneler] if aboneler else []
        print(f"--- BULUNAN ABONE SAYISI: {len(alici_listesi)} ---")

        threading.Thread(
            target=eposta_gonder_arkaplan,
            args=(baslik, alici_listesi)
        ).start()

    except Exception as e:
        print(f"--- MAIL HAZIRLAMA HATASI: {e} ---")

    flash('Makale ve medya başarıyla eklendi!', 'success')
    return redirect(url_for('index'))

@app.route('/makale-sil/<int:id>', methods=['POST'])
def makale_sil(id):
    if not session.get('admin'):
        return redirect(url_for('index'))

    baglanti = sqlite3.connect(VERITABANI)
    baglanti.execute("DELETE FROM makaleler WHERE id = ?", (id,))
    baglanti.commit()
    baglanti.close()

    flash('Makale silindi.', 'warning')
    return redirect(url_for('index'))

@app.route('/yorum-ekle/<int:makale_id>', methods=['POST'])
def yorum_ekle(makale_id):
    yazar = request.form.get('yazar')
    yorum = request.form.get('yorum')

    baglanti = sqlite3.connect(VERITABANI)
    baglanti.execute("INSERT INTO yorumlar (makale_id, yazar, yorum) VALUES (?, ?, ?)",
                     (makale_id, yazar, yorum))
    baglanti.commit()
    baglanti.close()

    return redirect(url_for('index'))

@app.route('/abone-ol', methods=['POST'])
def abone_ol():
    eposta = request.form.get('eposta')
    if eposta:
        try:
            baglanti = sqlite3.connect(VERITABANI)
            baglanti.execute("INSERT INTO aboneler (eposta) VALUES (?)", (eposta,))
            baglanti.commit()
            baglanti.close()
            flash('Bültene başarıyla abone oldunuz! Teşekkürler.', 'success')
        except sqlite3.IntegrityError:
            flash('Bu e-posta adresi zaten kayıtlı.', 'info')
        except Exception as e:
            flash('Bir hata oluştu, lütfen tekrar deneyin.', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
