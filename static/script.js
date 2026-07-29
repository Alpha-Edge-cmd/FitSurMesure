// Identifiant unique à cette session de questionnaire : envoyé avec toutes les
// requêtes (aperçu puis paiement) pour garantir un programme varié à chaque
// nouvelle génération, même si la personne retape exactement les mêmes
// informations de profil (nom, date de naissance, poids, taille...). Reste
// stable entre l'aperçu et le PDF final d'une même commande.
function _generateNonce() {
  if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
  return "nonce-" + Date.now() + "-" + Math.random().toString(36).slice(2);
}

const formData = {
  blessures: [],
  severite_blessure: {},
  exercices_incapables: [],
  exercices_maitrises: [],
  complements: [],
  aliments_apprecies: [],
  muscles_prioritaires: [],
  cardio_types: [],
  formule: "les_deux",
  exercices_rejetes: [],
  cardio_rejets: [],
  _nonce: _generateNonce(),
};

// Options de sévérité pour la question "à quel point cette gêne te limite-t-elle
// aujourd'hui ?" (une par zone cochée dans "blessures") — mêmes libellés que
// logic/profile_normalizer.py attend en clair, aucune traduction/code numérique.
const SEVERITE_OPTIONS = ["Légère gêne occasionnelle", "Gêne modérée régulière", "Douleur invalidante"];

// État de l'écran de révision ("je n'aime pas cet exercice / cette séance"),
// affiché après la dernière étape du questionnaire et avant génération du PDF.
let reviewMode = false;
let previewData = null;
// Prompt hors 24 phases ("Régénérer toute cette séance") : exclusions
// ajoutées par ce bouton, tenues à part de `formData.exercices_rejetes`.
// Raison : `collectReviewRejections()` (appelée juste avant le paiement final)
// RECONSTRUIT `formData.exercices_rejetes` uniquement à partir des cases à
// cocher actuellement affichées — or un exercice qu'on vient de faire exclure
// via "régénérer la séance" n'est justement PLUS affiché (il a disparu du
// nouvel aperçu) : sans cette liste séparée, fusionnée à chaque collecte,
// cette exclusion serait silencieusement perdue au moment de payer.
let regeneratedExclusions = [];

const RAISONS_EXERCICE = [
  "Je n'aime pas ce mouvement",
  "Douleur / gêne",
  "Je n'ai pas le matériel nécessaire",
  "Trop difficile / technique",
  "Autre",
];
// Prompt hors 24 phases : "en plus de pouvoir modifier les exercices, laisser
// une chance à l'algorithme si toute la séance ne plaît pas" — raison dédiée
// pour "Régénérer toute cette séance", VOLONTAIREMENT distincte de "Douleur /
// gêne" (qui exclut aussi tout le schéma de mouvement côté serveur, cf.
// app.py::_build_program_v2) : ici on veut juste d'autres exercices, pas
// nécessairement écarter tout le mouvement pour les prochaines générations.
const RAISON_REGENERATION_SEANCE = "Je veux une séance différente (régénération complète)";
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
          // Prompt hors 24 phases (retour Samy : "créer un programme
          // alimentation moins cher que le programme cardio avec également
          // un questionnaire adapté ne fais pas la même erreur") : nouvelle
          // offre dédiée, sans musculation ni cardio -- questionnaire adapté
          // via les mêmes conditions `showIf` que "cardio" ci-dessus (voir
          // toutes les questions musculation/cardio-spécifiques plus bas,
          // désormais masquées pour cette formule aussi).
          { value: "nutrition", label: "Programme Alimentation seul" },
          { value: "les_deux", label: "Programme Complet (Musculation + Cardio)" },
          { value: "abonnement", label: "Abonnement annuel (programmes illimités)" },
        ] },
    ],
  },
  // ---- Catégorie 1/7 : Profil général --------------------------------------
  {
    title: "Profil général",
    fields: [
      { id: "prenom", label: "Prénom (facultatif)", type: "text", placeholder: "Ex : Antonio" },
      { id: "date_naissance", label: "Date de naissance", type: "date-parts", required: true },
      { id: "sexe", label: "Sexe", type: "select", required: true,
        options: ["Homme", "Femme"] },
      { id: "poids", label: "Poids (kg)", type: "number", required: true, min: 30, max: 300 },
      { id: "taille", label: "Taille (cm)", type: "number", required: true, min: 100, max: 250 },
      // Prompt hors 24 phases (retour Samy : "un qlq de sec n'est pas
      // forcément mince, mets sec ensuite mince ensuite gras ensuite musclé
      // et gras ensuite athlétique") : options élargies et distinctes plutôt
      // que "sec / mince" regroupés en une seule, dans l'ordre demandé.
      { id: "composition_corporelle", label: "Comment décrirais-tu ton corps actuellement ?", type: "select",
        options: [
          "Sec / bien défini, peu de gras visible",
          "Mince / plutôt menu(e), naturellement peu de masse",
          "En surpoids / du gras à perdre",
          "Musclé(e) avec du gras à perdre (recomposition)",
          "Athlétique / sportif(ve), assez équilibré(e)",
          "Je ne sais pas",
        ] },
      { id: "niveau_musculation",
        label: d => d.formule === "nutrition"
          ? "Ton niveau de pratique sportive actuel"
          : "Niveau en musculation",
        type: "select", required: true,
        options: ["Débutant complet", "Quelques mois d'expérience", "Intermédiaire", "Avancé"] },
      // Retour Samy (séparation stricte des programmes) : question purement
      // musculation, sans effet sur les calculs nutritionnels — masquée en
      // formule Alimentation seule.
      { id: "annees_pratique", label: "Depuis combien de temps pratiques-tu la musculation régulièrement ? (facultatif)",
        type: "select",
        showIf: d => d.formule !== "nutrition",
        options: ["Moins de 6 mois", "6 mois à 2 ans", "2 à 5 ans", "Plus de 5 ans"] },
      // As-tu déjà testé ton 1RM (record perso) sur ces 4 mouvements de référence ?
      // Sert à calibrer le conseil d'exécution (cf. logic/recommendation/prescription.py,
      // conseil_execution) : monter progressivement si jamais testé, ou se
      // caler sur un pourcentage connu du record si déjà testé.
      { id: "pr_developpe_couche_barre", label: "As-tu déjà testé ton record perso (1RM) au développé couché à la barre ?",
        type: "select", options: ["Non", "Oui"], showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition") },
      { id: "pr_developpe_couche_haltere", label: "As-tu déjà testé ton record perso (1RM) au développé couché aux haltères ?",
        type: "select", options: ["Non", "Oui"], showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition") },
      { id: "pr_squat_barre", label: "As-tu déjà testé ton record perso (1RM) au squat à la barre ?",
        type: "select", options: ["Non", "Oui"], showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition") },
      { id: "pr_souleve_de_terre", label: "As-tu déjà testé ton record perso (1RM) au soulevé de terre ?",
        type: "select", options: ["Non", "Oui"], showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition") },
    ],
  },
  // ---- Catégorie 2/7 : Objectifs --------------------------------------------
  {
    title: "Objectifs",
    fields: [
      // Plusieurs objectifs peuvent être cochés en même temps (ex: Prise de
      // muscle + Force + Perte de gras) : le moteur calcule un objectif
      // composite à partir de TOUS les choix cochés (cf. logic/recommendation/
      // objectives.py, pondération dynamique). Remplace l'ancien select unique
      // "objectif_principal" (conservé côté backend pour compatibilité, déduit
      // automatiquement du premier choix coché).
      { id: "objectifs", label: "Tes objectifs (plusieurs choix possibles)", type: "checkbox-group", required: true,
        options: ["Prise de muscle", "Perte de gras", "Recomposition (sec + muscle)",
                   "Performance / explosivité", "Condition physique générale", "Gagner en force"] },
      { id: "objectif_secondaire", label: "Un objectif annexe, en plus de ceux ci-dessus ? (facultatif)",
        type: "select",
        options: ["Aucun", "Améliorer ma mobilité",
                   "Corriger un déséquilibre postural", "Préparer un événement (compétition, vacances...)"] },
      { id: "niveau_activite_quotidien", label: "Activité quotidienne hors sport", type: "select", required: true,
        options: [
          { value: "sedentaire", label: "Assis toute la journée (bureau, études)" },
          { value: "modere", label: "Actif modérément (debout, marche régulière)" },
          { value: "actif", label: "Très actif (métier physique, manuel)" },
        ] },
      { id: "pratique_cardio", label: "Pratique déjà un cardio en plus (course, vélo...)", type: "select",
        options: ["Non", "Oui"],
        showIf: d => d.formule === "musculation" },
      // Prompt hors 24 phases (retour Samy : "adapte le questionnaire pour
      // le cardio (course à pied, natation, vélo, circuit training cardio
      // en salle)") : "Circuit training" ajouté comme discipline explicite
      // (auparavant fondu dans "Autre", jamais distingué -- même erreur que
      // celle déjà commise avec la nutrition non séparée, à ne pas répéter).
      { id: "cardio_types", label: "Type(s) de cardio (plusieurs choix possibles)", type: "checkbox-group",
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule) || d.pratique_cardio === "Oui",
        options: ["Course", "Vélo", "Natation", "Circuit training (cardio en salle)", "Autre"] },
      { id: "cardio_frequence", label: "Fréquence du cardio souhaitée", type: "select",
        options: ["1x / semaine", "2x / semaine", "3x / semaine ou plus", "4x / semaine", "5x / semaine"],
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule) || d.pratique_cardio === "Oui" },
      { id: "objectif_cardio", label: "Objectif cardio spécifique", type: "select", required: true,
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule),
        options: ["Perdre du poids / sécher", "Améliorer mon endurance générale",
                   "Me préparer à une course (5km, 10km, semi, marathon)", "Santé cardiovasculaire générale"] },
      { id: "niveau_cardio", label: "Ton niveau actuel en cardio", type: "select", required: true,
        showIf: d => ["cardio", "les_deux", "abonnement"].includes(d.formule),
        options: ["Débutant", "Intermédiaire", "Confirmé"] },

      // ---- Sous-questions par discipline (prompt hors 24 phases, retour
      // Samy : "ajoute question type objectif dans course à pied, natation
      // ou vélo... quel objectif, par exemple la personne choisit course à
      // pied, pose des questions sur la course, dans combien de temps,
      // objectif d'allure ou autre, quels sont les records sur 5km, 10km,
      // 20km, 40km, laisse une possibilité aucun record") : chaque bloc n'est
      // visible que si la discipline correspondante est cochée ci-dessus.
      // Les records sont des nombres LIBRES (minutes) : un champ laissé vide
      // équivaut explicitement à "aucun record" (pas besoin d'une case à
      // part), demandé tel quel par Samy.
      { id: "objectif_course", label: "Course à pied — quel est ton objectif ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Course"),
        options: ["Courir plus longtemps sans m'arrêter", "Aller plus vite sur une distance donnée",
                   "Tenir une allure cible régulière", "Préparer une course (5km/10km/semi/marathon)",
                   "Perte de poids par la course", "Santé cardiovasculaire générale"] },
      { id: "delai_objectif_course", label: "Dans combien de temps veux-tu atteindre cet objectif ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Course"),
        options: ["Pas de délai précis", "1 mois", "2 à 3 mois", "6 mois", "1 an ou plus"] },
      { id: "allure_cible_course", label: "Allure cible visée, ou autre précision (facultatif)", type: "text",
        placeholder: "Ex : 5:30/km, ou \"tenir 10km sans marcher\"",
        showIf: d => (d.cardio_types || []).includes("Course") },
      // Retour Samy : question ajoutée juste sous l'allure cible. C'est la
      // donnée qui manquait le plus au moteur cardio — sans distance visée, il
      // ne pouvait pas placer d'allure spécifique (5 km, 10 km, semi, marathon)
      // ni doser la sortie longue, et retombait sur "endurance fondamentale"
      // par défaut. Cf. logic/cardio_builder.py::_session_mix.
      { id: "distance_objectif_course", label: "Sur combien de kilomètres ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Course"),
        options: [
          { value: "", label: "Pas de distance précise" },
          { value: "5km", label: "5 km" },
          { value: "10km", label: "10 km" },
          { value: "semi", label: "Semi-marathon (21,1 km)" },
          { value: "marathon", label: "Marathon (42,2 km)" },
          { value: "trail_ultra", label: "Trail / ultra (au-delà du marathon)" },
        ] },
      { id: "temps_1km", label: "Temps estimé sur 1 km de course (en minutes, ex : 5.5) — aide à mieux calibrer ton niveau",
        type: "number", placeholder: "Ex : 5.5",
        showIf: d => (d.cardio_types || []).includes("Course") },
      { id: "record_5km", label: "Ton record (temps) sur 5 km, en minutes — laisse vide si aucun record", type: "number",
        placeholder: "Ex : 25", showIf: d => (d.cardio_types || []).includes("Course") },
      { id: "record_10km", label: "Ton record (temps) sur 10 km, en minutes — laisse vide si aucun record", type: "number",
        placeholder: "Ex : 52", showIf: d => (d.cardio_types || []).includes("Course") },
      { id: "record_20km", label: "Ton record (temps) sur 20 km, en minutes — laisse vide si aucun record", type: "number",
        placeholder: "Ex : 115", showIf: d => (d.cardio_types || []).includes("Course") },
      { id: "record_40km", label: "Ton record (temps) sur 40 km (marathon), en minutes — laisse vide si aucun record",
        type: "number", placeholder: "Ex : 240", showIf: d => (d.cardio_types || []).includes("Course") },

      { id: "objectif_natation", label: "Natation — quel est ton objectif ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Natation"),
        options: ["Nager plus longtemps sans m'arrêter", "Aller plus vite sur une distance donnée",
                   "Améliorer ma technique / aisance dans l'eau", "Perte de poids par la natation",
                   "Santé cardiovasculaire générale"] },
      { id: "delai_objectif_natation", label: "Dans combien de temps veux-tu atteindre cet objectif ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Natation"),
        options: ["Pas de délai précis", "1 mois", "2 à 3 mois", "6 mois", "1 an ou plus"] },
      { id: "record_500m_natation", label: "Ton record (temps) sur 500 m, en minutes — laisse vide si aucun record",
        type: "number", placeholder: "Ex : 10", showIf: d => (d.cardio_types || []).includes("Natation") },
      { id: "record_1km_natation", label: "Ton record (temps) sur 1 km, en minutes — laisse vide si aucun record",
        type: "number", placeholder: "Ex : 22", showIf: d => (d.cardio_types || []).includes("Natation") },

      { id: "objectif_velo", label: "Vélo — quel est ton objectif ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Vélo"),
        options: ["Rouler plus longtemps", "Aller plus vite sur une distance donnée",
                   "Tenir une cadence / allure cible", "Perte de poids par le vélo",
                   "Santé cardiovasculaire générale"] },
      { id: "delai_objectif_velo", label: "Dans combien de temps veux-tu atteindre cet objectif ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Vélo"),
        options: ["Pas de délai précis", "1 mois", "2 à 3 mois", "6 mois", "1 an ou plus"] },
      { id: "record_20km_velo", label: "Ton record (temps) sur 20 km, en minutes — laisse vide si aucun record",
        type: "number", placeholder: "Ex : 40", showIf: d => (d.cardio_types || []).includes("Vélo") },
      { id: "record_40km_velo", label: "Ton record (temps) sur 40 km, en minutes — laisse vide si aucun record",
        type: "number", placeholder: "Ex : 80", showIf: d => (d.cardio_types || []).includes("Vélo") },

      { id: "objectif_circuit", label: "Circuit training (cardio en salle) — quel est ton objectif ?", type: "select",
        showIf: d => (d.cardio_types || []).includes("Circuit training (cardio en salle)"),
        options: ["Perte de poids", "Endurance générale", "Santé cardiovasculaire générale",
                   "Diversifier mon cardio (éviter la monotonie)"] },
      { id: "type_circuit_prefere", label: "Machines/formats que tu préfères (plusieurs choix possibles, facultatif)",
        type: "checkbox-group",
        showIf: d => (d.cardio_types || []).includes("Circuit training (cardio en salle)"),
        options: ["Tapis de course", "Vélo elliptique / spinning", "Rameur", "Stepper / escalier",
                   "Cours collectif (HIIT, step...)", "Mix de machines cardio"] },
    ],
  },
  // ---- Catégorie 3/7 : Morphologie ------------------------------------------
  {
    title: "Morphologie",
    fields: [
      { id: "longueur_bras", label: "Longueur de tes bras par rapport à ton buste (aide à choisir entre barre et haltères)",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Je ne sais pas", "Plutôt courts", "Moyens", "Plutôt longs"] },
      { id: "longueur_jambes", label: "Longueur de tes jambes par rapport à ton buste (aide à choisir ta variante de squat/soulevé de terre)",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Je ne sais pas", "Plutôt courtes", "Équilibrées", "Plutôt longues"] },
      { id: "longueur_buste", label: "Ton buste est-il plutôt long ou court par rapport à tes jambes ?",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Je ne sais pas", "Plutôt court", "Équilibré", "Plutôt long"] },
      { id: "largeur_epaules", label: "Comment décrirais-tu la largeur de tes épaules par rapport à ta cage thoracique ?",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Je ne sais pas", "Plutôt étroites", "Moyennes", "Plutôt larges"] },
      { id: "particularites_morphologiques", label: "Une particularité qui pourrait influencer certains exercices ? (facultatif)",
        type: "textarea",
        placeholder: "Ex : hyperlaxité, scoliose légère, une jambe plus courte que l'autre...",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition") },
    ],
  },
  // ---- Catégorie 4/7 : Mobilité et technique ---------------------------------
  {
    title: "Mobilité et technique",
    fields: [
      { id: "mobilite_generale", label: "Comment évaluerais-tu ta mobilité générale (chevilles, hanches, épaules) ?",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: [
          { value: "1", label: "1 — Très raide" }, { value: "2", label: "2" },
          { value: "3", label: "3 — Moyenne" }, { value: "4", label: "4" },
          { value: "5", label: "5 — Très mobile" },
        ] },
      { id: "amplitude_squat", label: "Arrives-tu à descendre confortablement en squat complet (cuisses sous parallèle) sans lever les talons ?",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Oui, facilement", "Avec difficulté", "Non, pas du tout"] },
      { id: "amplitude_epaule", label: "Arrives-tu à lever les bras complètement au-dessus de la tête sans cambrer le dos ?",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Oui, facilement", "Avec difficulté", "Non, pas du tout"] },
      { id: "tolerance_technique", label: "Es-tu à l'aise pour apprendre des mouvements techniquement exigeants (ex : soulevé de terre, olympique...) ?",
        type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: [
          { value: "1", label: "1 — Je préfère rester simple" }, { value: "2", label: "2" },
          { value: "3", label: "3 — Ça dépend" }, { value: "4", label: "4" },
          { value: "5", label: "5 — J'adore apprendre des mouvements techniques" },
        ] },
      { id: "exercices_maitrises", label: "Parmi ces mouvements, lesquels maîtrises-tu techniquement ? (facultatif)",
        type: "checkbox-group",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Squat barre", "Soulevé de terre", "Développé couché barre", "Tractions",
                   "Développé militaire barre", "Aucun de ces mouvements"] },
    ],
  },
  // ---- Catégorie 5/7 : Contraintes physiques ---------------------------------
  {
    title: "Contraintes physiques",
    fields: [
      // Retour Samy (séparation stricte) : les douleurs articulaires servent à
      // écarter des exercices de musculation et à adapter les séances cardio.
      // Elles n'ont aucune incidence sur un plan alimentaire seul.
      { id: "blessures", label: "Douleurs ou blessures actuelles", type: "checkbox-group",
        showIf: d => d.formule !== "nutrition",
        options: ["Épaule", "Dos / lombaires", "Genoux", "Chevilles / talons", "Poignets"] },
      { id: "severite_blessure", label: "À quel point ces gênes te limitent-elles aujourd'hui ?",
        type: "severity-per-zone", zonesField: "blessures",
        showIf: d => d.formule !== "nutrition" && (d.blessures || []).length > 0 },
      { id: "exercices_incapables", label: "Exercices qu'il ne sait pas / ne peut pas faire", type: "checkbox-group",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Tractions", "Dips", "Squat barre libre", "Soulevé de terre barre"] },
      { id: "precisions", label: "Précisions (facultatif)", type: "textarea",
        showIf: d => d.formule !== "nutrition",
        placeholder: "Ex : sensibilité au talon droit à la course" },
    ],
  },
  // ---- Catégorie 6/7 : Organisation entraînement -----------------------------
  {
    title: "Organisation entraînement",
    fields: [
      { id: "frequence_entrainement", label: "Fréquence de musculation souhaitée", type: "select", required: true,
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: [
          { value: "2", label: "2x / semaine" }, { value: "3", label: "3x / semaine" },
          { value: "4", label: "4x / semaine" }, { value: "5", label: "5x / semaine" },
          { value: "6", label: "6x / semaine" },
        ] },
      { id: "duree_seance", label: "Durée max par séance", type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["45 min", "1h", "1h - 1h30", "1h30+"] },
      { id: "disponibilite_reelle", label: "En réalité, combien de temps peux-tu consacrer à l'entraînement par semaine, tout compris ? (facultatif)",
        type: "select",
        showIf: d => d.formule !== "nutrition",
        options: ["Moins de 2h", "2 à 4h", "4 à 6h", "Plus de 6h"] },
      { id: "split_preference", label: "Split préféré", type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: [
          { value: "auto", label: "Laisse l'algorithme choisir" },
          { value: "full_body", label: "Full Body" },
          { value: "upper_lower", label: "Upper / Lower" },
          { value: "ppl", label: "Push / Pull / Legs" },
          { value: "arnold", label: "Arnold Split" },
          { value: "ppl_upper_lower", label: "Push / Pull / Legs + Upper / Lower (5 jours)" },
        ] },
      // Prompt hors 24 phases (retour Samy : "y a-t-il un ou plusieurs
      // programmes que vous ne souhaitez pas avoir et seulement et
      // uniquement dans ce cas là le nombre de jours d'entraînement choisi
      // ne dépend plus du programme") : distinct de "split_preference"
      // ci-dessus (qui choisit UN split précis) -- ici on exclut un ou
      // plusieurs types de programme, l'algorithme choisit alors librement
      // parmi ceux qui restent, sans être contraint par le barème habituel
      // fréquence -> split (cf. logic/program_builder.py::_split_key_selectionne).
      { id: "splits_exclus", label: "Y a-t-il un ou plusieurs types de programme que tu NE souhaites PAS avoir ? (facultatif)",
        type: "checkbox-group",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: [
          { value: "full_body", label: "Full Body" },
          { value: "upper_lower", label: "Upper / Lower" },
          { value: "ppl", label: "Push / Pull / Legs" },
          { value: "arnold", label: "Arnold Split" },
          { value: "ppl_upper_lower", label: "Push / Pull / Legs + Upper / Lower (5 jours)" },
        ] },
      // Prompt hors 24 phases (retour Samy, refonte du volume) : le nombre
      // d'exercices par muscle n'est plus demandé manuellement — l'algorithme
      // le détermine désormais lui-même (position de priorité du muscle +
      // nombre de portions anatomiques à couvrir, cf. logic/recommendation/
      // volume.py::calculer_repartition_seance). Champ "exos_par_muscle_pref"
      // retiré du questionnaire (Samy : "ne demande plus combien d'exercice
      // on veut bosser par muscle") ; conservé côté backend (app.py) comme
      // repli "auto" pour l'ancien moteur legacy uniquement (jamais lu par le
      // moteur V2), donc rien à migrer côté données existantes.
      { id: "muscles_prioritaires", label: "Groupes musculaires à prioriser (facultatif, plus de volume leur sera donné)",
        type: "checkbox-group",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Pectoraux", "Dos", "Épaules", "Bras (biceps/triceps)", "Jambes (quadriceps/ischio)", "Fessiers", "Abdominaux"] },
      { id: "autre_sport", label: "Pratiques-tu un autre sport en parallèle (foot, tennis, danse...) ?",
        type: "select", options: ["Non", "Oui"] },
      { id: "autre_sport_type", label: "Lequel ?", type: "select",
        options: [
          "Football", "Tennis", "Basketball",
          "Sports de combat (boxe, MMA, kickboxing...)",
          "Arts martiaux (judo, karaté, taekwondo...)",
          "Athlétisme / course à pied", "Rugby", "Natation", "Cyclisme",
          "Handball", "Volleyball", "Danse", "Escalade", "Golf", "Autre",
        ],
        showIf: d => d.autre_sport === "Oui" },
      { id: "autre_sport_type_autre", label: "Précise lequel", type: "text", placeholder: "Ex : Aviron",
        showIf: d => d.autre_sport === "Oui" && d.autre_sport_type === "Autre" },
      { id: "autre_sport_frequence", label: "À quelle fréquence ?", type: "select",
        options: ["1x / semaine", "2x / semaine", "3x / semaine ou plus"],
        showIf: d => d.autre_sport === "Oui" },
      { id: "autre_sport_adapter", label: "Veux-tu que ton programme de musculation soit adapté à ce sport (davantage de volume sur les muscles qu'il sollicite le plus) ?",
        type: "select", options: ["Non", "Oui"],
        showIf: d => d.autre_sport === "Oui" },
      { id: "sommeil", label: "Sommeil moyen par nuit", type: "select",
        options: ["Moins de 6h", "6 à 7h", "7 à 8h", "8h et plus"] },
      { id: "niveau_stress", label: "Niveau de stress actuel", type: "select",
        options: ["Faible", "Modéré", "Élevé"] },
    ],
  },
  // ---- Catégorie 7/7 : Préférences -------------------------------------------
  {
    title: "Préférences",
    fields: [
      { id: "equipement", label: "Équipement disponible", type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Salle complète", "Surtout machines guidées", "Surtout poids libres",
                   "Matériel limité à domicile"] },
      { id: "preference_materiel", label: "Si tu as le choix, tu préfères plutôt travailler avec : (plusieurs choix possibles, facultatif)",
        type: "checkbox-group",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Barres libres", "Haltères", "Machines guidées"] },
      { id: "preference_style_charge", label: "Tu préfères plutôt : (facultatif)", type: "select",
        showIf: d => (d.formule !== "cardio" && d.formule !== "nutrition"),
        options: ["Soulever lourd, peu de répétitions", "Contrôler le mouvement, plus de répétitions",
                   "Un mix des deux"] },
      { id: "preferences_libres", label: "Autre chose à préciser sur tes préférences d'entraînement ? (facultatif)",
        type: "textarea", showIf: d => d.formule !== "nutrition",
        placeholder: "Ex : je préfère éviter les longues séries de cardio en fin de séance" },
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
      // Retour Samy : "Poulet" et "Dinde" ajoutés explicitement. "Volaille"
      // est conservé pour qui veut cocher large (canard, pintade...), mais les
      // deux viandes blanches de loin les plus consommées en musculation
      // méritent leur propre case plutôt que d'être noyées dans une catégorie
      // générique — elles orientent des suggestions de repas différentes.
      { id: "aliments_apprecies", label: "Catégories d'aliments que tu apprécies (pour orienter les suggestions)",
        type: "checkbox-group",
        options: ["Poulet", "Dinde", "Volaille (autre)", "Viande rouge", "Poisson", "Œufs",
                   "Légumineuses", "Produits laitiers", "Fruits à coque"] },
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
      // sommeil / niveau_stress ont déménagé dans "Organisation entraînement"
      // (catégorie 6/7) — ce sont des variables moteur, elles vivent maintenant
      // au même endroit que fréquence/durée/disponibilité réelle.
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

// Vrai quand l'utilisateur arrive depuis la landing page avec une formule déjà
// choisie (?formule=...) : l'étape 0 "Ta formule" est alors sautée, et sans
// point de retour explicite il n'existait aucun moyen de revenir au menu des
// programmes (retour Samy). Cf. `preselectFormule()` en bas de fichier et le
// lien "← Changer de programme" ajouté dans l'en-tête d'étape.
let formulePreselectionnee = false;

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

// Libellé lisible de la formule en cours ("musculation" -> "Programme
// Musculation seul"), lu directement dans les options de l'étape 0 pour ne pas
// dupliquer la liste des offres.
function formuleLabel(valeur) {
  const champ = steps[0].fields.find(f => f.id === "formule");
  const option = (champ ? champ.options : []).find(o => optionValue(o) === valeur);
  return option ? optionLabel(option) : "";
}

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
  if (f.type === "date-parts") {
    // Remplace l'ancien <input type="date"> : sur mobile (iOS notamment), un
    // input date natif s'affiche en molette qu'il faut faire défiler année
    // par année depuis la date du jour — très pénible pour remonter à une
    // date de naissance (retour Samy, prompt hors 24 phases). Trois <select>
    // indépendants (jour/mois/année) permettent d'aller directement à
    // l'année voulue sans défilement complet.
    const current = val || "";
    const [yActuelle, mActuelle, dActuelle] = current.split("-");
    const jours = Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, "0"));
    const moisNoms = [
      ["01", "Janvier"], ["02", "Février"], ["03", "Mars"], ["04", "Avril"],
      ["05", "Mai"], ["06", "Juin"], ["07", "Juillet"], ["08", "Août"],
      ["09", "Septembre"], ["10", "Octobre"], ["11", "Novembre"], ["12", "Décembre"],
    ];
    const anneeActuelle = new Date().getFullYear();
    // De 10 à 100 ans : couvre tous les profils réalistes du questionnaire,
    // sans obliger à défiler jusqu'en l'an 1900.
    const annees = Array.from({ length: 91 }, (_, i) => String(anneeActuelle - 10 - i));

    const optJour = ['<option value="">Jour</option>'].concat(
      jours.map(j => `<option value="${j}" ${dActuelle === j ? "selected" : ""}>${j}</option>`)
    ).join("");
    const optMois = ['<option value="">Mois</option>'].concat(
      moisNoms.map(([v, l]) => `<option value="${v}" ${mActuelle === v ? "selected" : ""}>${l}</option>`)
    ).join("");
    const optAnnee = ['<option value="">Année</option>'].concat(
      annees.map(a => `<option value="${a}" ${yActuelle === a ? "selected" : ""}>${a}</option>`)
    ).join("");

    return `<div class="date-parts-grid">
      <select data-field="${f.id}" data-date-part="jour">${optJour}</select>
      <select data-field="${f.id}" data-date-part="mois">${optMois}</select>
      <select data-field="${f.id}" data-date-part="annee">${optAnnee}</select>
    </div>`;
  }
  if (f.type === "checkbox-group") {
    const arr = formData[f.id] || [];
    // Correctif (retour Samy) : les options d'un checkbox-group peuvent être
    // soit des chaînes ("Course", "Vélo"...), soit des objets
    // { value, label } — c'est le cas de "splits_exclus", seul groupe du
    // questionnaire dans ce format. L'ancienne version interpolait `o`
    // directement, ce qui affichait "[object Object]" et enregistrait la
    // chaîne "[object Object]" comme valeur cochée. On passe désormais par
    // les mêmes helpers optionValue()/optionLabel() que les <select>.
    return `<div class="checkbox-grid">${f.options.map(o => {
      const v = optionValue(o), l = optionLabel(o);
      return `
      <label>
        <input type="checkbox" data-field="${f.id}" value="${v}" ${arr.includes(v) ? "checked" : ""}>
        ${l}
      </label>`;
    }).join("")}</div>`;
  }
  if (f.type === "textarea") {
    return `<textarea rows="2" data-field="${f.id}" placeholder="${f.placeholder || ""}">${val || ""}</textarea>`;
  }
  if (f.type === "severity-per-zone") {
    // Une case à cocher par zone déjà déclarée dans f.zonesField (ex: "blessures"),
    // pas une seule valeur — ce champ n'a donc pas de formData[f.id] scalaire comme
    // les autres, mais un objet {zone: sévérité}. Rempli/lu directement dans formData.
    const zones = formData[f.zonesField] || [];
    if (!formData[f.id]) formData[f.id] = {};
    if (!zones.length) return "";
    return `<div class="severity-grid">${zones.map(zone => {
      const current = formData[f.id][zone] || "";
      const opts = ['<option value="">-- choisir --</option>'].concat(
        SEVERITE_OPTIONS.map(o => `<option value="${o}" ${current === o ? "selected" : ""}>${o}</option>`)
      );
      return `
        <div class="severity-row">
          <span class="severity-zone">${zone}</span>
          <select data-severity-zone="${zone}" data-field="${f.id}">${opts.join("")}</select>
        </div>`;
    }).join("")}</div>`;
  }
  const min = f.min !== undefined ? `min="${f.min}"` : "";
  const max = f.max !== undefined ? `max="${f.max}"` : "";
  return `<input type="${f.type}" data-field="${f.id}" placeholder="${f.placeholder || ""}" value="${val || ""}" ${min} ${max}>`;
}

function renderStep() {
  const s = steps[current];
  const container = document.getElementById("steps");
  const visibleFields = s.fields.filter(f => !f.showIf || f.showIf(formData));

  // Flèche de retour au menu des programmes (retour Samy : "lorsqu'on
  // sélectionne un programme, ajoute une petite flèche de retour en arrière
  // afin de revenir facilement au menu précédent"). Affichée dès qu'on a
  // dépassé l'étape "Ta formule", que celle-ci ait été franchie normalement
  // ou sautée via ?formule=... depuis la landing page. Le libellé rappelle la
  // formule en cours pour que l'utilisateur voie immédiatement s'il s'est
  // trompé de programme.
  const retourMenuHtml = current > 0
    ? `<button type="button" class="back-to-menu" id="backToMenu"
         title="Revenir au choix du programme">&larr; Changer de programme${
           formuleLabel(formData.formule) ? ` (${formuleLabel(formData.formule)})` : ""
         }</button>`
    : "";

  let html = `
    ${retourMenuHtml}
    <div class="step-header">
      <span class="step-count">Étape ${current + 1} sur ${steps.length}</span>
      <h2>${s.title}</h2>
    </div>
  `;
  visibleFields.forEach(f => {
    // `label` accepte une fonction (d => "...") pour les rares questions dont
    // la formulation doit s'adapter à la formule choisie — cf.
    // "niveau_musculation", conservée en formule Alimentation parce qu'elle
    // alimente réellement le calcul des protéines et l'ajustement calorique
    // (logic/calculations.py), mais qui ne doit pas être formulée en termes de
    // musculation dans un programme purement nutritionnel.
    const labelTexte = typeof f.label === "function" ? f.label(formData) : f.label;
    html += `<div class="field"><label>${labelTexte}</label>${fieldHtml(f)}</div>`;
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

  // Selects de sévérité par zone (champ "severity-per-zone") : traités à part,
  // car ils écrivent dans un objet imbriqué (formData.severite_blessure[zone]),
  // pas dans formData[f.id] directement comme un select classique.
  container.querySelectorAll("[data-severity-zone]").forEach(el => {
    el.addEventListener("change", () => {
      const zone = el.dataset.severityZone;
      const key = el.dataset.field;
      if (!formData[key]) formData[key] = {};
      formData[key][zone] = el.value;
    });
  });

  // Trois <select> jour/mois/année (champ "date-parts") : recompose la date
  // ISO complète depuis les 3 sélecteurs de son propre groupe à chaque
  // changement, plutôt que d'écraser formData[f.id] avec la seule valeur du
  // <select> modifié (ce qu'aurait fait le gestionnaire générique ci-dessous).
  container.querySelectorAll(".date-parts-grid").forEach(grid => {
    const selects = grid.querySelectorAll("select[data-date-part]");
    const key = selects[0].dataset.field;
    selects.forEach(sel => {
      sel.addEventListener("change", () => {
        const parts = {};
        selects.forEach(s => { parts[s.dataset.datePart] = s.value; });
        formData[key] = (parts.jour && parts.mois && parts.annee)
          ? `${parts.annee}-${parts.mois}-${parts.jour}`
          : "";
      });
    });
  });

  container.querySelectorAll("[data-field]:not([data-severity-zone]):not([data-date-part])").forEach(el => {
    if (el.type === "checkbox") {
      el.addEventListener("change", () => {
        const key = el.dataset.field;
        if (!Array.isArray(formData[key])) formData[key] = [];
        if (el.checked) {
          if (!formData[key].includes(el.value)) formData[key].push(el.value);
        } else {
          formData[key] = formData[key].filter(v => v !== el.value);
          // Zone décochée : on nettoie sa sévérité éventuelle pour ne pas garder
          // une donnée orpheline (zone plus déclarée mais sévérité toujours stockée).
          if (key === "blessures" && formData.severite_blessure) {
            delete formData.severite_blessure[el.value];
          }
        }
        // Une case à cocher ne fait perdre aucun focus de saisie (contrairement à un
        // champ texte/nombre en cours de frappe) : on peut re-render sans risque. C'est
        // nécessaire pour les champs conditionnés par une checkbox-group (ex : sévérité
        // par zone de blessure), et corrige au passage la réactivité de "temps au km"
        // (dépendait déjà de cardio_types sans jamais se ré-afficher avant ce changement).
        renderStep();
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

  // Retour direct au choix du programme, quel que soit le nombre d'étapes déjà
  // franchies. Les réponses déjà saisies sont conservées : changer de formule
  // ne fait que modifier les questions affichées (via les `showIf`), donc
  // repartir de zéro punirait inutilement quelqu'un qui s'est juste trompé de
  // programme au départ.
  const backToMenuEl = document.getElementById("backToMenu");
  if (backToMenuEl) {
    backToMenuEl.addEventListener("click", () => {
      current = 0;
      renderStep();
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
    // `label` peut être une fonction (libellé dépendant de la formule choisie,
    // cf. renderStep) : on le résout avant de l'insérer dans un message
    // d'erreur, sinon l'utilisateur lirait "[object Function]".
    const nom = typeof f.label === "function" ? f.label(formData) : f.label;
    // checkbox-group : un tableau vide est "truthy" en JS ([] est vrai), donc
    // le test générique ci-dessous ne suffit pas — vérifie explicitement la
    // longueur (utilisé notamment par le nouveau champ "objectifs", plusieurs
    // choix possibles, prompt final hors 24 phases).
    if (f.required && f.type === "checkbox-group" && (!formData[f.id] || formData[f.id].length === 0)) {
      showMessage(`Merci de sélectionner au moins une option pour : ${nom}`, "error");
      return false;
    }
    if (f.required && f.type !== "checkbox-group" && !formData[f.id]) {
      showMessage(`Merci de renseigner : ${nom}`, "error");
      return false;
    }
    if (f.type === "number" && formData[f.id]) {
      const v = parseFloat(formData[f.id]);
      if (f.min !== undefined && v < f.min) { showMessage(`${nom} trop faible.`, "error"); return false; }
      if (f.max !== undefined && v > f.max) { showMessage(`${nom} trop élevé.`, "error"); return false; }
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
      html += `
        <div class="review-session-header">
          <h4>${jour.nom}</h4>
          <button type="button" class="btn-secondary btn-regenerate-session" data-jour="${jour.nom}">
            🔁 Régénérer toute cette séance
          </button>
        </div>
      `;
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

  // Prompt hors 24 phases : "Régénérer toute cette séance" — au lieu de cocher
  // exercice par exercice, on ajoute d'un coup TOUS les exercices actuellement
  // affichés pour cette séance à `exercices_rejetes` (même mécanisme déjà
  // existant que le rejet individuel, cf. app.py::_build_program_v2, qui
  // exclut ces exercices précis du prochain tirage), puis on redemande
  // immédiatement un nouvel aperçu au serveur pour que l'algorithme propose
  // d'autres exercices pour cette séance.
  container.querySelectorAll(".btn-regenerate-session").forEach(btn => {
    btn.addEventListener("click", async () => {
      const nomJour = btn.dataset.jour;
      const jour = (previewData.program.programme || []).find(j => j.nom === nomJour);
      if (!jour) return;

      const nomsDeLaSeance = new Set();
      jour.muscles.forEach(bloc => bloc.exercices.forEach(nom => nomsDeLaSeance.add(nom)));

      const dejaRejetes = new Set(regeneratedExclusions.map(r => r.nom));
      nomsDeLaSeance.forEach(nom => {
        if (!dejaRejetes.has(nom)) {
          regeneratedExclusions.push({ nom, raison: RAISON_REGENERATION_SEANCE });
        }
      });
      formData.exercices_rejetes = regeneratedExclusions.concat(
        formData.exercices_rejetes.filter(r => !dejaRejetes.has(r.nom))
      );

      btn.disabled = true;
      btn.textContent = "Régénération en cours...";
      await showReview();
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

  // Fusionne avec les exclusions posées par "Régénérer toute cette séance"
  // (cf. `regeneratedExclusions`) : ces exercices ne sont plus affichés comme
  // cases à cocher (ils ont déjà disparu du nouvel aperçu), donc absents de
  // `exercicesRejetes` ci-dessus — sans cette fusion, ils seraient perdus au
  // moment de payer.
  const nomsDejaCollectes = new Set(exercicesRejetes.map(r => r.nom));
  regeneratedExclusions.forEach(r => {
    if (!nomsDejaCollectes.has(r.nom)) exercicesRejetes.push(r);
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
// (?formule=nutrition|musculation|cardio|les_deux|abonnement), on la
// préremplit et on saute directement à l'étape suivante.
//
// Correctif (retour Samy : "il y a des questions de musculation dans le
// programme alimentation") : "nutrition" manquait dans cette liste alors que
// la landing page propose bien un lien /questionnaire?formule=nutrition. La
// formule n'était donc jamais appliquée et formData.formule restait à sa
// valeur par défaut ("les_deux"), ce qui affichait TOUT le questionnaire
// musculation + cardio à quelqu'un venu pour le programme Alimentation seul.
// La liste est désormais dérivée des options réellement déclarées dans
// l'étape "Ta formule", pour qu'un futur ajout d'offre ne puisse plus
// réintroduire ce décalage.
const FORMULES_VALIDES = (steps[0].fields.find(f => f.id === "formule").options || [])
  .map(optionValue);

(function preselectFormule() {
  const params = new URLSearchParams(window.location.search);
  const formule = params.get("formule");
  if (formule && FORMULES_VALIDES.includes(formule)) {
    formData.formule = formule;
    current = 1;
    formulePreselectionnee = true;
  }
})();

renderStep();
