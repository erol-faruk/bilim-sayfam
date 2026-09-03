from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "super_gizli_yonetici_anahtari"
YONETICI_SIFRESI = "123456"
VERITABANI = "bilim.db"


def veritabani_hazirla():
    baglanti = sqlite3.connect(VERITABANI)

    # Makaleler Tablosu
    baglanti.execute("""
        CREATE TABLE IF NOT EXISTS makaleler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            link TEXT NOT NULL,
            aciklama TEXT,
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


@app.route("/login", methods=["POST"])
def login():
    if request.form.get("sifre") == YONETICI_SIFRESI:
        session["admin_giris"] = True
    return redirect(url_for("ana_sayfa"))


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
