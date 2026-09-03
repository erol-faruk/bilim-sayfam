const aramaKutusu = document.getElementById("aramaKutusu");
const makaleKartlari = document.querySelectorAll(".makale-karti");

aramaKutusu.addEventListener("input", function() {
    const aramaMetni = aramaKutusu.value.toLowerCase();

    makaleKartlari.forEach(function(kart) {
        const kartMetni = kart.textContent.toLowerCase();

        if (kartMetni.includes(aramaMetni)) {
            kart.style.display = "block";
        } else {
            kart.style.display = "none";
        }
    });
});
