# -*- coding: utf-8 -*-
"""
Échauffement et étirements liés à l'objectif annexe déclaré.

Retour Samy : « dans la question où on peut répondre "améliorer ma mobilité",
propose un ou deux exercices en échauffement et/ou en étirement pour
l'améliorer — et pareil si la personne sélectionne une autre réponse. Je veux
vraiment que chaque question posée ait un rapport avec le programme. »

La question `objectif_secondaire` était bien collectée et reconnue par
`profile_normalizer`, mais aucune de ses trois réponses ne produisait le
moindre contenu dans le PDF. Elle relevait donc exactement du cas qu'il
décrivait : une question qui n'a aucun rapport avec le programme livré.

Chaque objectif annexe donne maintenant deux blocs concrets :
  - un ÉCHAUFFEMENT, à faire avant la séance, qui prépare les articulations
    réellement concernées ;
  - des ÉTIREMENTS, à faire après, sur les zones que l'objectif vise.

Choix de conception : on ne touche PAS à la sélection des exercices. Un
objectif annexe est annexe — il ne doit pas déformer un programme construit
pour l'objectif principal. Il ajoute du contenu autour de la séance, là où
c'est utile et sans risque.

Repères retenus, cohérents avec la pratique courante : mobilité dynamique
avant l'effort (les étirements statiques prolongés avant une séance réduisent
temporairement la production de force), étirements statiques après, tenus 30
à 45 secondes.
"""

MOBILITE = "Améliorer ma mobilité"
POSTURE = "Corriger un déséquilibre postural"
EVENEMENT = "Préparer un événement (compétition, vacances...)"


PROTOCOLES = {
    MOBILITE: {
        "titre": "Ton objectif annexe : améliorer ta mobilité",
        "intro": (
            "La mobilité progresse par la répétition quotidienne, pas par des séances "
            "dédiées occasionnelles. Ces deux blocs prennent moins de 10 minutes et se "
            "greffent sur tes séances existantes."
        ),
        "echauffement": [
            ("Rotations de hanches en fente (2 x 8 par côté)",
             "En position de fente basse, pose la main au sol côté jambe avant et fais "
             "tourner le bassin d'avant en arrière. Ouvre la hanche là où le squat et les "
             "fentes te limitent."),
            ("Dislocations d'épaules au bâton ou à l'élastique (2 x 10)",
             "Bras tendus, passe un bâton de l'avant vers l'arrière au-dessus de la tête, "
             "en écartant les mains autant qu'il le faut pour ne jamais forcer. Resserre "
             "la prise au fil des semaines."),
            ("Accroupissement profond tenu (3 x 30 secondes)",
             "Descends aussi bas que possible, talons au sol, coudes à l'intérieur des "
             "genoux pour les écarter doucement. C'est le test et l'exercice à la fois."),
        ],
        "etirements": [
            ("Étirement des fléchisseurs de hanche (30-45 sec par côté)",
             "En fente genou au sol, bascule le bassin vers l'avant en serrant le fessier "
             "du côté étiré. C'est la zone la plus raccourcie chez qui reste assis."),
            ("Étirement des ischio-jambiers assis (30-45 sec par côté)",
             "Jambe tendue, dos droit, penche-toi depuis la hanche et non depuis le dos."),
            ("Étirement pectoraux au montant de porte (30-45 sec par côté)",
             "Avant-bras contre le montant, coude à hauteur d'épaule, avance le buste. "
             "Ouvre la poitrine et compense les positions fermées de la journée."),
        ],
    },

    POSTURE: {
        "titre": "Ton objectif annexe : corriger un déséquilibre postural",
        "intro": (
            "Un déséquilibre se corrige en renforçant ce qui est faible autant qu'en "
            "assouplissant ce qui est raide. Ces exercices ciblent le schéma le plus "
            "fréquent : épaules enroulées et bassin basculé vers l'avant."
        ),
        "echauffement": [
            ("Face pull à l'élastique (2 x 15)",
             "Tire l'élastique vers le visage en écartant les mains, coudes hauts. "
             "Réveille les rotateurs externes et l'arrière d'épaule, presque toujours "
             "sous-développés."),
            ("Dead bug (2 x 8 par côté)",
             "Allongé sur le dos, bas du dos plaqué au sol, tends bras et jambe opposés "
             "sans décoller les lombaires. Apprend au tronc à tenir la position neutre."),
            ("Pont fessier au sol (2 x 12)",
             "Monte le bassin en serrant les fessiers, sans cambrer. Réactive une chaîne "
             "postérieure souvent endormie par la position assise."),
        ],
        "etirements": [
            ("Étirement des fléchisseurs de hanche (30-45 sec par côté)",
             "Le contrepoids direct d'un bassin basculé vers l'avant."),
            ("Étirement du grand dorsal contre un support (30-45 sec par côté)",
             "Mains en appui haut, recule les hanches et laisse la poitrine descendre."),
            ("Étirement des trapèzes supérieurs (30-45 sec par côté)",
             "Incline la tête sur le côté, épaule opposée basse. À faire souvent si tu "
             "travailles sur écran."),
        ],
    },

    EVENEMENT: {
        "titre": "Ton objectif annexe : préparer un événement",
        "intro": (
            "Quand une échéance approche, l'échauffement compte double : une blessure à "
            "trois semaines de l'objectif coûte bien plus cher qu'une séance manquée. Ces "
            "blocs privilégient la préparation à l'effort plutôt que le gain de souplesse."
        ),
        "echauffement": [
            ("Montées de genoux et talons-fesses (2 x 20 secondes chacun)",
             "Élève la température et la fréquence cardiaque avant la première série."),
            ("Séries d'approche progressives (3 séries légères)",
             "Sur ton premier exercice, monte graduellement jusqu'à ta charge de travail. "
             "Ne commence jamais directement au poids cible à l'approche d'une échéance."),
            ("Mobilité articulaire ciblée (1 à 2 min)",
             "Épaules, hanches et chevilles : les trois articulations où une raideur se "
             "paie immédiatement en performance."),
        ],
        "etirements": [
            ("Retour au calme actif (5 min)",
             "Marche ou vélo très léger avant les étirements : la récupération commence "
             "là, pas sous la douche."),
            ("Étirements globaux légers (20-30 sec par zone)",
             "Reste court et doux à l'approche de l'événement. Ce n'est pas le moment de "
             "chercher du gain d'amplitude, ton corps doit rester prévisible."),
        ],
    },
}


def protocole_pour(objectif_secondaire):
    """Protocole d'échauffement et d'étirements, ou None si aucun objectif
    annexe n'a été déclaré (« Aucun » ou champ vide)."""
    return PROTOCOLES.get((objectif_secondaire or "").strip())
