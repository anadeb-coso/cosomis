
const CONTEXT_MENU_OPTIONS = [
    // --- Manipulation de Ligne / Colonne ---
    'row_above',       // Insère une ligne au-dessus
    'row_below',       // Insère une ligne en dessous
    'remove_row',      // Supprime la/les ligne(s) sélectionnée(s)
    'col_left',        // Insère une colonne à gauche
    'col_right',       // Insère une colonne à droite
    //'remove_col',      // Supprime la/les colonne(s) sélectionnée(s)
    
    '---------',       // Séparateur visuel
    
    // --- Édition / Historique ---
    'undo',            // Annuler
    'redo',            // Rétablir
    'cut',             // Couper
    'copy',            // Copier
    
    '---------',
    
    // --- Mise en page / Formatage ---
    'alignment',       // Sous-menu pour l'alignement du texte
    'mergeCells',      // Sous-menu pour la fusion/séparation de cellules
    'make_read_only',  // Rendre la sélection en lecture seule
    // 'comments',        // Sous-menu pour la gestion des commentaires
    
    '---------',
    
    // --- Affichage ---
    // 'hidden_columns',  // Sous-menu pour masquer/afficher des colonnes
    // 'hidden_rows'      // Sous-menu pour masquer/afficher des lignes
];

const DROPDOWN_MENU_OPTIONS = [
    // --- Tri (nécessite 'columnSorting: true') ---
    //'sort_asc',            // Tri ascendant
    //'sort_desc',           // Tri descendant
    //'column_only',         // Option de tri pour les tris multi-colonnes
    
    '---------',

    'col_left',        // Insère une colonne à gauche
    'col_right',       // Insère une colonne à droite
    // 'remove_col',      // Supprime la/les colonne(s) sélectionnée(s)
    'clear_column',    // Efface le contenu de la colonne sélectionnée

    '---------',

    // --- Affichage ---
    // 'hidden_columns',  // Sous-menu pour masquer/afficher des colonnes

    '---------',
    
    // --- Filtres (nécessite 'filters: true') ---
    'filter_by_condition', // Sous-menu pour les filtres par condition
    'filter_by_value',     // Sous-menu pour les filtres par valeur (checkboxes)
    'filter_action_bar'    // Barre d'actions pour appliquer/annuler les filtres
];