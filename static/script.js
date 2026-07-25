const formData = {
  blessures: [],
  exercices_incapables: [],
  complements: [],
  aliments_apprecies: [],
  muscles_prioritaires: [],
  cardio_types: [],
  formule: "les_deux",
  exercices_rejetes: [],
  cardio_rejets: [],
};

// État de l'écran de révision ("je n'aime pas cet exercice / cette séance"),
// affiché après la dernière étape du questionnaire et avant génération du PDF.
let reviewMode = false;
let previewData = null;

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

const steps = [
  {
    title: "Ta formule",
    fields: [
      { id: "formule", label: "Quelle formule veux-tu ?", type: "select", required: true,
        options: [
          { value: "musculation", label: "Programme Musculation seul" },
          { value: "cardio", label: "Programme Cardio seul" },
          { value: "les_deux", label: "Programme Complet (Musculation + Cardio)" },
          { value: "abonnement", label: "Abonnement annuel (programmes illimités)" },
        ] },
    ],
  },
  {
    title: "Profil",
    fields: [
      { id: "prenom", label: "Prénom (facultatif)", type: "text", placeholder: "Ex : Antonio" },
      { id: "date_naissance", label: "Date de naissance", type: "date", required: true },
      { id: "sexe", label: "Sexe", type: "select", required: true,
        options: ["Homme", "Femme"] },
      { id: "poids", label: "Poids (kg)", type: "number", required: true, min: 30, max: 300 },
      { id: "taille", label: "Taille (cm)", type: "number", required: true, min: 100, max: 250 },
      { id: "composition_corporelle", label: "Comment décrirais-tu ton corps actuellement ?", type: "select",
        options: ["Plutôt sec / mince", "Plutôt en surpoids / du gras à perdre",
                   "Musclé(e) avec du gras à perdre (recomposition)", "Je ne sais pas"] },
    ],
  },
  {
    title: "Niveau et objectif",
    fields: [
      { id: "niveau_musculation", label: "Niveau en musculation", type: "select", required: true,
        options: ["Débutant complet", "Quelques mois d'expérience", "Intermédiaire", "Avancé"] },
      { id: "objectif_principal", label: "Objectif principal", type: "select", required: true,
        options: ["Prise de muscle", "Perte de gras", "Recomposition (sec + muscle)",
                   "Performance / explosivité", "Condition physique générale"] },
      { id: "niveau_activite_quotidien", label: "Activité quotidienne hors sport", type: "select", required: true,
        options: [
          { value: "sedentaire", label: "Assis toute la journée (bureau, études)" },
          { value: "modere", label: "Actif modérément (debout, marche régulière)" },
          { value: "actif", label: "Très actif (métier physique, manuel)" },
        ] },
      { id: "pratique_cardio", label: "Pratique déjà un cardio en plus (course, vélo...)", type: "select",
        options: ["Non", "Oui"],
        showIf: d => d.formule === "musculation" },
      { id: "cardio_types", label: "Type(s) de cardio (plusieurs choix possibles)", type: "checkbox-group",
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule) || d.pratique_cardio === "Oui",
        options: ["Course", "Vélo", "Natation", "Autre"] },
      { id: "cardio_frequence", label: "Fréquence du cardio souhaitée", type: "select",
        options: ["1x / semaine", "2x / semaine", "3x / semaine ou plus"],
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule) || d.pratique_cardio === "Oui" },
      { id: "objectif_cardio", label: "Objectif cardio spécifique", type: "select", required: true,
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule),
        options: ["Perdre du poids / sécher", "Améliorer mon endurance générale",
                   "Me préparer à une course (5km, 10km, semi, marathon)", "Santé cardiovasculaire générale"] },
      { id: "temps_1km", label: "Temps estimé sur 1 km de course (en minutes, ex : 5.5) — aide à mieux calibrer ton niveau",
        type: "number", placeholder: "Ex : 5.5",
        showIf: d => (d.cardio_types || []).includes("Course") },
      { id: "niveau_cardio", label: "Ton niveau actuel en cardio", type: "select", required: true,
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule),
        options: ["Débutant", "Intermédiaire", "Confirmé"] },
      { id: "autre_sport", label: "Pratiques-tu un autre sport en parallèle (foot, tennis, danse...) ?",
        type: "select", options: ["Non", "Oui"] },
      { id: "autre_sport_type", label: "Lequel ?", type: "text", placeholder: "Ex : Football",
        showIf: d => d.autre_sport === "Oui" },
      { id: "autre_sport_frequence", label: "À quelle fréquence ?", type: "select",
        options: ["1x / semaine", "2x / semaine", "3x / semaine ou plus"],
        showIf: d => d.autre_sport === "Oui" },
    ],
  },
  {
    title: "Entraînement",
    fields: [
      { id: "frequence_entrainement", label: "Fréquence de musculation souhaitée", type: "select", required: true,
        showIf: d => d.formule !== "cardio",
        options: [
          { value: "2", label: "2x / semaine" }, { value: "3", label: "3x / semaine" },
          { value: "4", label: "4x / semaine" }, { value: "5", label: "5x / semaine" },
          { value: "6", label: "6x / semaine" },
        ] },
      { id: "duree_seance", label: "Durée max par séance", type: "select",
        showIf: d => d.formule !== "cardio",
        options: ["45 min", "1h", "1h - 1h30", "1h30+"] },
      { id: "split_preference", label: "Split préféré", type: "select",
        showIf: d => d.formule !== "cardio",
        options: [
          { value: "auto", label: "Laisse l'algorithme choisir" },
          { value: "full_body", label: "Full Body" },
          { value: "upper_lower", label: "Upper / Lower" },
          { value: "ppl", label: "Push / Pull / Legs" },
          { value: "arnold", label: "Arnold Split" },
        ] },
      { id: "equipement", label: "Équipement disponible", type: "select",
        showIf: d => d.formule !== "cardio",
        options: ["Salle complète", "Surtout machines guidées", "Surtout poids libres",
                   "Matériel limité à domicile"] },
      { id: "exos_par_muscle_pref", label: "Nombre d'exercices par muscle souhaité", type: "select",
        showIf: d => d.formule !== "cardio",
        options: [
          { value: "auto", label: "Laisse l'algorithme décider" },
          { value: "2", label: "2 par muscle" },
          { value: "3", label: "3 par muscle" },
          { value: "4", label: "4 par muscle" },
        ] },
      { id: "muscles_prioritaires", label: "Groupes musculaires à prioriser (facultatif, plus de volume leur sera donné)",
        type: "checkbox-group",
        showIf: d => d.formule !== "cardio",
        options: ["Pectoraux", "Dos", "Épaules", "Bras (biceps/triceps)", "Jambes (quadriceps/ischio)", "Fessiers", "Abdominaux"] },
    ],
  },
  {
    title: "Contraintes physiques",
    fields: [
      { id: "blessures", label: "Douleurs ou blessures actuelles", type: "checkbox-group",
        options: ["Épaule", "Dos / lombaires", "Genoux", "Chevilles / talons", "Poignets"] },
      { id: "exercices_incapables", label: "Exercices qu'il ne sait pas / ne peut pas faire", type: "checkbox-group",
        showIf: d => d.formule !== "cardio",
        options: ["Tractions", "Dips", "Squat barre libre", "Soulevé de terre barre"] },
      { id: "longueur_bras", label: "Longueur de tes bras par rapport à ton buste (aide à choisir entre barre et haltères)",
        type: "select",
        showIf: d => d.formule !== "cardio",
        options: ["Je ne sais pas", "Plutôt courts", "Moyens", "Plutôt longs"] },
      { id: "longueur_jambes", label: "Longueur de tes jambes par rapport à ton buste (aide à choisir ta variante de squat/soulevé de terre)",
        type: "select",
        showIf: d => d.formule !== "cardio",
        options: ["Je ne sais pas", "Plutôt courtes", "Équilibrées", "Plutôt longues"] },
      { id: "precisions", label: "Précisions (facultatif)", type: "textarea",
        placeholder: "Ex : sensibilité au talon droit à la course" },
    ],
  },
  {
    title: "Alimentation",
    fields: [
      { id: "restriction_alimentaire", label: "Restriction alimentaire", type: "select",
        options: ["Aucune", "Végétarien", "Végan", "Sans lactose", "Sans gluten", "Allergie"] },
      { id: "allergie_details", label: "Précise ton/tes allergie(s)", type: "text",
        placeholder: "Ex : arachides, fruits de mer",
        showIf: d => d.restriction_alimentaire === "Allergie" },
      { id: "aliments_apprecies", label: "Catégories d'aliments que tu apprécies (pour orienter les suggestions)",
        type: "checkbox-group",
        options: ["Viande rouge", "Volaille", "Poisson", "Œufs", "Légumineuses", "Produits laitiers", "Fruits à coque"] },
      { id: "aliments_non_apprecies", label: "Aliments ou ingrédients précis non appréciés", type: "text",
        placeholder: "Ex : tomates, brocolis" },
      { id: "repas_par_jour", label: "Repas par jour souhaités", type: "select",
        options: ["2 à 3", "3 à 4", "4 à 5"] },
      { id: "temps_cuisine", label: "Temps disponible pour cuisiner", type: "select",
        options: ["Peu de temps (recettes rapides)", "Le temps qu'il faut"] },
      { id: "budget_alimentaire", label: "Budget alimentaire", type: "select",
        options: ["Serré", "Confortable"] },
    ],
  },
  {
    title: "Mode de vie et compléments",
    fields: [
      { id: "sommeil", label: "Sommeil moyen par nuit", type: "select",
        options: ["Moins de 6h", "6 à 7h", "7 à 8h", "8h et plus"] },
      { id: "niveau_stress", label: "Niveau de stress actuel", type: "select",
        options: ["Faible", "Modéré", "Élevé"] },
      { id: "tabac", label: "Tabac (cigarette classique)", type: "select",
        options: ["Non", "Occasionnel", "Régulier"] },
      { id: "cigarette_electronique", label: "Cigarette électronique / vapote", type: "select",
        options: ["Non", "Occasionnel", "Régulier"] },
      { id: "cannabis", label: "Cannabis", type: "select", options: ["Non", "Occasionnel", "Régulier"] },
      { id: "alcool", label: "Alcool", type: "select", options: ["Jamais", "Occasionnel", "Régulier"] },
      { id: "complements", label: "Compléments souhaités", type: "checkbox-group",
        options: ["Créatine", "Whey", "Oméga-3", "Vitamine D", "Magnésium / ZMA",
                   "Béta-alanine", "Multivitamines", "Fer", "Collagène", "BCAA/EAA",
                   "Caféine / pré-workout", "Autre"] },
    ],
  },
  {
    title: "Santé et consentement",
    fields: [
      { id: "condition_medicale", label: "As-tu une condition médicale ou un traitement en cours ?", type: "select",
        options: ["Non", "Oui"] },
      { id: "condition_medicale_details", label: "Précise (facultatif)", type: "textarea",
        showIf: d => d.condition_medicale === "Oui" },
      { id: "grossesse", label: "Grossesse en cours ?", type: "select", options: ["Non", "Oui"],
        showIf: d => d.sexe === "Femme" },
      { id: "code_promo", label: "Code promo / parrainage (facultatif)", type: "text",
        placeholder: "Ex : KARIM-7F3B" },
    ],
    consentAtEnd: true,
  },
];

let current = 0;

function renderProgress() {
  const bar = document.getElementById("progress");
  bar.innerHTML = "";
  steps.forEach((s, i) => {
    const dot = document.createElement("div");
    dot.className = i < current ? "done" : (i === current ? "active" : "");
    bar.appendChild(dot);
  });
}

function optionValue(o) { return typeof o === "string" ? o : o.value; }
function optionLabel(o) { return typeof o === "string" ? o : o.label; }

function fieldHtml(f) {
  const val = formData[f.id];
  if (f.type === "select") {
    const opts = ['<option value="">-- choisir --</option>'].concat(
      f.options.map(o => {
        const v = optionValue(o), l = optionLabel(o);
        const sel = val === v ? "selected" : "";
        return `<option value="${v}" ${sel}>${l}</option>`;
      })
    );
    return `<select data-field="${f.id}">${opts.join("")}</select>`;
  }
  if (f.type === "checkbox-group") {
    const arr = formData[f.id] || [];
    return `<div class="checkbox-grid">${f.options.map(o => `
      <label>
        <input type="checkbox" data-field="${f.id}" value="${o}" ${arr.includes(o) ? "checked" : ""}>
        ${o}
      </label>`).join("")}</div>`;
  }
  if (f.type === "textarea") {
    return `<textarea rows="2" data-field="${f.id}" placeholder="${f.placeholder || ""}">${val || ""}</textarea>`;
  }
  const min = f.min !== undefined ? `min="${f.min}"` : "";
  const max = f.max !== undefined ? `max="${f.max}"` : "";
  return `<input type="${f.type}" data-field="${f.id}" placeholder="${f.placeholder || ""}" value="${val || ""}" ${min} ${max}>`;
}

function renderStep() {
  const s = steps[current];
  const container = document.getElementById("steps");
  const visibleFields = s.fields.filter(f => !f.showIf || f.showIf(formData));

  let html = `
    <div class="step-header">
      <span class="step-count">Étape ${current + 1} sur ${steps.length}</span>
      <h2>${s.title}</h2>
    </div>
  `;
  visibleFields.forEach(f => {
    html += `<div class="field"><label>${f.label}</label>${fieldHtml(f)}</div>`;
  });

  if (s.consentAtEnd) {
    html += `
      <div class="consent-box">
        <input type="checkbox" id="consentBox" ${formData.consentement_rgpd ? "checked" : ""}>
        <label for="consentBox">
          J'accepte que mes données (âge, poids, santé) soient utilisées uniquement pour générer
          ce programme personnalisé, conformément au RGPD. Ce document ne remplace pas un avis
          médical.
        </label>
      </div>
    `;
  }

  container.innerHTML = html;

  container.querySelectorAll("[data-field]").forEach(el => {
    if (el.type === "checkbox") {
      el.addEventListener("change", () => {
        const key = el.dataset.field;
        if (!Array.isArray(formData[key])) formData[key] = [];
        if (el.checked) {
          if (!formData[key].includes(el.value)) formData[key].push(el.value);
        } else {
          formData[key] = formData[key].filter(v => v !== el.value);
        }
      });
    } else if (el.tagName === "SELECT") {
      // Un select change en une seule action (pas de perte de focus possible) :
      // on peut se permettre de re-render pour afficher/masquer les champs conditionnels.
      el.addEventListener("change", () => {
        formData[el.dataset.field] = el.value;
        renderStep();
      });
    } else {
      // text / number / date / textarea : on mémorise la position du curseur et on ne
      // re-render JAMAIS la liste complète sur chaque frappe (sinon le champ perd le
      // focus après chaque lettre). Aucun de ces champs ne conditionne l'affichage
      // d'un autre champ, donc pas besoin de renderStep() ici.
      el.addEventListener("input", () => {
        formData[el.dataset.field] = el.value;
      });
    }
  });

  const consentEl = document.getElementById("consentBox");
  if (consentEl) {
    consentEl.addEventListener("change", () => {
      formData.consentement_rgpd = consentEl.checked;
    });
  }

  document.getElementById("backBtn").style.visibility = current === 0 ? "hidden" : "visible";
  const nextBtn = document.getElementById("nextBtn");
  nextBtn.innerHTML = current === steps.length - 1 ? "Voir mon programme →" : "Suivant";
  document.getElementById("messageBox").innerHTML = "";

  renderProgress();
}

function validateStep() {
  const s = steps[current];
  const visibleFields = s.fields.filter(f => !f.showIf || f.showIf(formData));
  for (const f of visibleFields) {
    if (f.required && !formData[f.id]) {
      showMessage(`Merci de renseigner : ${f.label}`, "error");
      return false;
    }
    if (f.type === "number" && formData[f.id]) {
      const v = parseFloat(formData[f.id]);
      if (f.min !== undefined && v < f.min) { showMessage(`${f.label} trop faible.`, "error"); return false; }
      if (f.max !== undefined && v > f.max) { showMessage(`${f.label} trop élevé.`, "error"); return false; }
    }
  }
  if (s.consentAtEnd && !formData.consentement_rgpd) {
    showMessage("Le consentement RGPD est nécessaire pour générer ton programme.", "error");
    return false;
  }
  return true;
}

function showMessage(text, type) {
  const box = document.getElementById("messageBox");
  box.innerHTML = `<div class="${type === "error" ? "error-box" : "success-box"}">${text}</div>`;
}

// ---------------- Écran de révision "je n'aime pas cet exercice / cette séance" ----------------
// Avant de générer le PDF final, on montre à la personne la liste réelle des exercices
// et séances de cardio qui ont été choisis pour elle, pour qu'elle puisse signaler ce
// qu'elle n'aime pas (et pourquoi) et obtenir un programme ajusté en conséquence.

async function showReview() {
  const container = document.getElementById("steps");
  const nextBtn = document.getElementById("nextBtn");
  nextBtn.disabled = true;
  nextBtn.innerHTML = '<span class="spinner"></span> Préparation de ton programme...';

  try {
    const res = await fetch("/generate-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
    const data = await res.json().catch(() => null);

    if (!res.ok || !data) {
      showMessage((data && data.error) || "Impossible de préparer l'aperçu, tu peux quand même passer au paiement.", "error");
      nextBtn.disabled = false;
      return submitForm();
    }

    if (data.blocked) {
      // Programme bloqué pour raison de sécurité (cf. nutrition) : pas de révision
      // possible, on passe directement au paiement (le PDF expliquera pourquoi).
      nextBtn.disabled = false;
      return submitForm();
    }

    previewData = data;
    reviewMode = true;
    renderReview();
  } catch (e) {
    showMessage("Impossible de contacter le serveur, tu peux réessayer.", "error");
    nextBtn.disabled = false;
    nextBtn.innerHTML = "Payer et recevoir mon PDF";
  }
}

function reasonSelectHtml(groupName, itemKey, options) {
  return `
    <select data-group="${groupName}" data-item="${itemKey}">
      ${options.map(o => `<option value="${o}">${o}</option>`).join("")}
    </select>
  `;
}

function renderReview() {
  const container = document.getElementById("steps");
  let html = `
    <div class="step-header">
      <span class="step-count">Dernière étape</span>
      <h2>Une remarque sur ton programme ?</h2>
    </div>
    <p class="review-intro">
      Voici les exercices et séances de cardio retenus pour toi. Si certains ne te
      conviennent pas, coche-les et précise pourquoi : on ajustera ton programme avant
      de générer le PDF final.
    </p>
  `;

  if (previewData.program) {
    html += `<div class="review-group"><h3>Musculation — ${previewData.program.split_label}</h3>`;
    previewData.program.programme.forEach(jour => {
      html += `<h4>${jour.nom}</h4>`;
      jour.muscles.forEach(bloc => {
        bloc.exercices.forEach(nom => {
          const key = `${jour.nom}::${bloc.muscle}::${nom}`;
          const checked = formData.exercices_rejetes.some(r => r.nom === nom);
          html += `
            <div class="review-item">
              <label class="review-item-label">
                <input type="checkbox" data-exo="${nom}" data-key="${key}" ${checked ? "checked" : ""}>
                ${nom} <span style="color:var(--grey); font-weight:400;">(${bloc.muscle})</span>
              </label>
              <div class="conditional ${checked ? "" : "hidden"}" data-conditional-for="${key}">
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
      const checked = formData.cardio_rejets.some(r => r.seance_nom === s.nom);
      html += `
        <div class="review-item">
          <label class="review-item-label">
            <input type="checkbox" data-cardio="${s.nom}" data-key="${key}" ${checked ? "checked" : ""}>
            ${s.nom} — ${s.discipline} (${s.type})
          </label>
          <div class="conditional ${checked ? "" : "hidden"}" data-conditional-for="${key}">
            ${reasonSelectHtml("cardio", key, RAISONS_CARDIO)}
          </div>
        </div>
      `;
    });
    html += `</div>`;
  }

  container.innerHTML = html;

  container.querySelectorAll("input[type=checkbox][data-key]").forEach(cb => {
    cb.addEventListener("change", () => {
      const cond = container.querySelector(`[data-conditional-for="${cb.dataset.key}"]`);
      if (cond) cond.classList.toggle("hidden", !cb.checked);
    });
  });

  document.getElementById("backBtn").style.visibility = "visible";
  const nextBtn = document.getElementById("nextBtn");
  nextBtn.disabled = false;
  nextBtn.innerHTML = "Payer et recevoir mon PDF";
  document.getElementById("messageBox").innerHTML = "";
  renderProgress();
}

function collectReviewRejections() {
  const container = document.getElementById("steps");
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

  formData.exercices_rejetes = exercicesRejetes;
  formData.cardio_rejets = cardioRejets;
}

// Au lieu de générer le PDF directement, on crée une commande côté serveur (qui
// garde les réponses du questionnaire) et on redirige soit vers Stripe Checkout
// (formules payantes), soit directement vers la page de confirmation (si un code
// promo valide rend le programme gratuit). Le téléchargement du PDF et la
// possibilité de modifier le programme après coup se font sur cette page de
// confirmation (/payment-success), pas ici.
async function submitForm() {
  const nextBtn = document.getElementById("nextBtn");
  nextBtn.disabled = true;
  nextBtn.innerHTML = '<span class="spinner"></span> Préparation du paiement...';

  try {
    const res = await fetch("/create-checkout-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });

    const data = await res.json().catch(() => null);

    if (!res.ok || !data) {
      showMessage((data && data.error) || "Une erreur est survenue.", "error");
      nextBtn.disabled = false;
      nextBtn.innerHTML = "Payer et recevoir mon PDF";
      return;
    }

    if (data.redirect_url) {
      window.location.href = data.redirect_url;
      return;
    }
    if (data.checkout_url) {
      window.location.href = data.checkout_url;
      return;
    }

    showMessage("Impossible de créer la session de paiement.", "error");
  } catch (e) {
    showMessage("Impossible de contacter le serveur.", "error");
  }

  nextBtn.disabled = false;
  nextBtn.innerHTML = "Payer et recevoir mon PDF";
}

function stepHasVisibleContent(s) {
  const visibleFields = s.fields.filter(f => !f.showIf || f.showIf(formData));
  return visibleFields.length > 0 || !!s.consentAtEnd;
}

// Certaines étapes (ex: "Entraînement" en formule Cardio seul) peuvent se retrouver
// entièrement vides selon la formule choisie : on les saute automatiquement.
function findStep(from, direction) {
  let i = from;
  while (i + direction >= 0 && i + direction <= steps.length - 1) {
    i += direction;
    if (stepHasVisibleContent(steps[i])) return i;
  }
  return null;
}

document.getElementById("nextBtn").addEventListener("click", () => {
  if (reviewMode) {
    collectReviewRejections();
    submitForm();
    return;
  }
  if (!validateStep()) return;
  const next = findStep(current, 1);
  if (next === null) {
    showReview();
  } else {
    current = next;
    renderStep();
  }
});

document.getElementById("backBtn").addEventListener("click", () => {
  if (reviewMode) {
    reviewMode = false;
    renderStep();
    return;
  }
  const prev = findStep(current, -1);
  if (prev !== null) {
    current = prev;
    renderStep();
  }
});

// Si on arrive depuis la landing page avec une formule déjà choisie
// (?formule=musculation|cardio|les_deux|abonnement), on la préremplit et on
// saute directement à l'étape suivante.
(function preselectFormule() {
  const params = new URLSearchParams(window.location.search);
  const formule = params.get("formule");
  if (formule && ["musculation", "cardio", "les_deux", "abonnement"].includes(formule)) {
    formData.formule = formule;
    current = 1;
  }
})();

renderStep();
