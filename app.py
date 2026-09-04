import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()
app = Flask(__name__)
app.secret_key = "super_gizli_yonetici_anahtari"
YONETICI_SIFRESI = "123456"
VERITABANI = "bilim.db"


def veritabani_hazirla():
    baglanti = sqlite3.connect(VERITABANI)

    # Makaleler Tablosu
    baglanti.execute("""CREATE TABLE IF NOT EXISTS makaleler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            icerik TEXT NOT NULL,
            dosya_url TEXT,
            dosya_turu TEXT,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
 """)

    # Yorumlar Tablosu
    baglanti.execute("""
        CREATE TABLE IF NOT EXISTS yorumlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            makale_id INTEGER NOT NULL,
            isim TEXT NOT NULL,
            yorum TEXT NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (makale_id) REFERENCES makaleler (id) ON DELETE CASCADE
        )
    """)

    baglanti.commit()
    baglanti.close()


def makaleleri_ve_yorumları_getir():
    baglanti = sqlite3.connect(VERITABANI)
    baglanti.row_factory = sqlite3.Row

    makaleler = baglanti.execute(
        "SELECT * FROM makaleler ORDER BY tarih DESC"
    ).fetchall()

    # Makaleleri ve onlara ait yorumları bir sözlük yapısında birleştiriyoruz
    makale_listesi = []
    for makale in makaleler:
        yorumlar = baglanti.execute(
            "SELECT * FROM yorumlar WHERE makale_id = ? ORDER BY tarih ASC",
            (makale["id"],),
        ).fetchall()

        makale_listesi.append({"makale": makale, "yorumlar": yorumlar})

    baglanti.close()
    return makale_listesi


@app.route("/")
def ana_sayfa():
    veri = makaleleri_ve_yorumları_getir()
    is_admin = session.get("admin_giris", False)
    return render_template("index.html", veri=veri, is_admin=is_admin)


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
    
    # GET isteği geldiğinde basit giriş formunu göster
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


@app.route("/logout")
def logout():
    session.pop("admin_giris", None)
    return redirect(url_for("ana_sayfa"))


@app.route("/makale-ekle", methods=["POST"])
def makale_ekle():
    if not session.get("admin_giris"):
        return "Yetkisiz erişim!", 403

    baslik = request.form["baslik"].strip()
    link = request.form["link"].strip()
    aciklama = request.form["aciklama"].strip()

    if baslik and link and link.startswith(("http://", "https://")):
        baglanti = sqlite3.connect(VERITABANI)
        baglanti.execute(
            "INSERT INTO makaleler (baslik, link, aciklama) VALUES (?, ?, ?)",
            (baslik, link, aciklama),
        )
        baglanti.commit()
        baglanti.close()

    return redirect(url_for("ana_sayfa"))


@app.route("/makale-sil/<int:makale_id>", methods=["POST"])
def makale_sil(makale_id):
    if not session.get("admin_giris"):
        return "Yetkisiz erişim!", 403

    baglanti = sqlite3.connect(VERITABANI)
    baglanti.execute("DELETE FROM makaleler WHERE id = ?", (makale_id,))
    baglanti.execute("DELETE FROM yorumlar WHERE makale_id = ?", (makale_id,))
    baglanti.commit()
    baglanti.close()

    return redirect(url_for("ana_sayfa"))


@app.route("/yorum-ekle/<int:makale_id>", methods=["POST"])
def yorum_ekle(makale_id):
    isim = request.form.get("isim", "").strip()
    yorum = request.form.get("yorum", "").strip()

    if isim and yorum:
        baglanti = sqlite3.connect(VERITABANI)
        baglanti.execute(
            "INSERT INTO yorumlar (makale_id, isim, yorum) VALUES (?, ?, ?)",
            (makale_id, isim, yorum),
        )
        baglanti.commit()
        baglanti.close()

    return redirect(url_for("ana_sayfa"))


@app.route("/yorum-sil/<int:yorum_id>", methods=["POST"])
def yorum_sil(yorum_id):
    if not session.get("admin_giris"):
        return "Yetkisiz erişim!", 403

    baglanti = sqlite3.connect(VERITABANI)
    baglanti.execute("DELETE FROM yorumlar WHERE id = ?", (yorum_id,))
    baglanti.commit()
    baglanti.close()

    return redirect(url_for("ana_sayfa"))


if __name__ == "__main__":
    veritabani_hazirla()
    app.run(host="0.0.0.0", port=5000, debug=True)
