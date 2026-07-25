// Fonctions partagées pour l'écran de révision "je n'aime pas cet exercice / cette
// séance", utilisées par la page de confirmation de paiement (payment_success.html)
// pour permettre d'ajuster le programme APRÈS paiement, sans repayer.
// (Le questionnaire lui-même, dans script.js, a sa propre copie de cette logique
// pour l'écran de révision AVANT paiement — volontairement non partagée pour ne
// pas risquer de régression sur ce flux déjà en place.)

const RAISONS_EXERCICE = [
  "Je n'aime pas ce mouvement",
  "Douleur / gêne",
  "Je n'ai pas le matériel nécessaire",
  "Trop difficile / technique",
  "Autre",
];
const RAISONS_CARDIO = [
  "Trop difficile / intense",
  "Je n'aime pas ce sport",
  "Autre",
];

function reasonSelectHtml(groupName, itemKey, options) {
  return `
    <select data-group="${groupName}" data-item="${itemKey}">
      ${options.map(o => `<option value="${o}">${o}</option>`).join("")}
    </select>
  `;
}

function renderReviewListHtml(previewData) {
  let html = "";

  if (previewData.program) {
    html += `<div class="review-group"><h3>Musculation — ${previewData.program.split_label}</h3>`;
    previewData.program.programme.forEach(jour => {
      html += `<h4>${jour.nom}</h4>`;
      jour.muscles.forEach(bloc => {
        bloc.exercices.forEach(nom => {
          const key = `${jour.nom}::${bloc.muscle}::${nom}`;
          html += `
            <div class="review-item">
              <label class="review-item-label">
                <input type="checkbox" data-exo="${nom}" data-key="${key}">
                ${nom} <span style="color:var(--grey); font-weight:400;">(${bloc.muscle})</span>
              </label>
              <div class="conditional hidden" data-conditional-for="${key}">
                ${reasonSelectHtml("exo", key, RAISONS_EXERCICE)}
              </div>
            </div>
          `;
        });
      });
    });
    html += `</div>`;
  }

  if (previewData.cardio) {
    html += `<div class="review-group"><h3>Cardio</h3>`;
    previewData.cardio.seances.forEach(s => {
      const key = s.nom;
      html += `
        <div class="review-item">
          <label class="review-item-label">
            <input type="checkbox" data-cardio="${s.nom}" data-key="${key}">
            ${s.nom} — ${s.discipline} (${s.type})
          </label>
          <div class="conditional hidden" data-conditional-for="${key}">
            ${reasonSelectHtml("cardio", key, RAISONS_CARDIO)}
          </div>
        </div>
      `;
    });
    html += `</div>`;
  }

  return html;
}

function attachReviewCheckboxHandlers(container) {
  container.querySelectorAll("input[type=checkbox][data-key]").forEach(cb => {
    cb.addEventListener("change", () => {
      const cond = container.querySelector(`[data-conditional-for="${cb.dataset.key}"]`);
      if (cond) cond.classList.toggle("hidden", !cb.checked);
    });
  });
}

function collectReviewRejectionsFromContainer(container) {
  const exercicesRejetes = [];
  const cardioRejets = [];

  container.querySelectorAll("input[data-exo]:checked").forEach(cb => {
    const select = container.querySelector(`select[data-group="exo"][data-item="${cb.dataset.key}"]`);
    exercicesRejetes.push({ nom: cb.dataset.exo, raison: select ? select.value : "Autre" });
  });
  container.querySelectorAll("input[data-cardio]:checked").forEach(cb => {
    const select = container.querySelector(`select[data-group="cardio"][data-item="${cb.dataset.key}"]`);
    cardioRejets.push({ seance_nom: cb.dataset.cardio, raison: select ? select.value : "Autre" });
  });

  return { exercicesRejetes, cardioRejets };
}
