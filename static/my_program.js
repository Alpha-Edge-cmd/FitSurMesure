// Phase 23/24 : boutons de feedback de l'interface /my-program.
// Appelle POST /my-program/action (JSON) en arrière-plan, sans recharger la
// page (important en mobile-first : éviter tout aller-retour de page sur un
// simple tap). Aucune logique de recommandation ici : ce fichier ne fait que
// relayer un clic vers le serveur.
document.querySelectorAll(".exo-action-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const exerciseId = btn.dataset.exerciseId;
    const action = btn.dataset.action;
    const card = btn.closest(".exo-card");
    const statusEl = card ? card.querySelector(".exo-status") : null;

    btn.disabled = true;
    if (statusEl) {
      statusEl.textContent = "Enregistrement...";
      statusEl.classList.remove("ok", "error");
    }

    try {
      const res = await fetch("/my-program/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exercise_id: exerciseId, action: action }),
      });
      const data = await res.json().catch(() => ({}));

      if (statusEl) {
        if (res.ok) {
          statusEl.textContent = "Enregistré ✓";
          statusEl.classList.add("ok");
        } else {
          statusEl.textContent = data.error || "Erreur, réessaie.";
          statusEl.classList.add("error");
        }
      }
    } catch (e) {
      if (statusEl) {
        statusEl.textContent = "Impossible de contacter le serveur.";
        statusEl.classList.add("error");
      }
    }

    btn.disabled = false;
    setTimeout(() => {
      if (statusEl) {
        statusEl.textContent = "";
        statusEl.classList.remove("ok", "error");
      }
    }, 3000);
  });
});
